from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DbSession, Manager, require_csrf
from app.models import (
    OfferStatus,
    Room,
    RoomStatus,
    Task,
    TaskOffer,
    TaskStatus,
    User,
    UserRole,
    UserStatus,
)
from app.services.assignment import (
    PRIORITY_RULES,
    AssignmentError,
    assign_directly,
    cancel_task,
    get_settings,
    process_due_work,
    retry_task,
    staff_workload,
)
from app.services.task_views import reference

router = APIRouter()
CSRF_DEPENDENCY = [Depends(require_csrf)]


class FloorRequest(BaseModel):
    floor: int | None = Field(default=None, ge=0, le=200)


class SettingsRequest(BaseModel):
    adjacent_floor_range: int = Field(ge=0, le=10)
    max_offer_attempts: int = Field(ge=1, le=20)
    offer_timeout_seconds: int = Field(ge=30, le=3600)
    max_active_tasks_per_staff: int = Field(ge=1, le=20)


class AssignRequest(BaseModel):
    staff_id: int


def _settings_view(db: DbSession) -> dict:
    config = get_settings(db)
    return {
        "adjacent_floor_range": config.adjacent_floor_range,
        "max_offer_attempts": config.max_offer_attempts,
        "offer_timeout_seconds": config.offer_timeout_seconds,
        "max_active_tasks_per_staff": config.max_active_tasks_per_staff,
        "priority_rules": PRIORITY_RULES,
    }


def _task(db: DbSession, task_id: int) -> Task:
    task = db.get(Task, task_id, with_for_update=True)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _run(db: DbSession, action) -> dict[str, str]:
    try:
        action()
    except AssignmentError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    db.commit()
    return {"message": "Updated"}


@router.get("/staff")
def list_staff(db: DbSession, _manager: Manager) -> list[dict]:
    process_due_work(db)
    staff = db.scalars(
        select(User)
        .where(User.role == UserRole.HOUSEKEEPING_STAFF, User.status == UserStatus.ACTIVE)
        .order_by(User.floor.is_(None), User.floor, User.email)
    ).all()
    workload = staff_workload(db, [member.id for member in staff])
    return [
        {
            "id": member.id,
            "email": member.email,
            "floor": member.floor,
            "is_available": member.is_available,
            "workload": workload[member.id],
        }
        for member in staff
    ]


@router.patch("/staff/{staff_id}", dependencies=CSRF_DEPENDENCY)
def allocate_floor(staff_id: int, payload: FloorRequest, db: DbSession, _manager: Manager) -> dict:
    member = db.get(User, staff_id)
    if member is None or member.role != UserRole.HOUSEKEEPING_STAFF:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    member.floor = payload.floor
    db.commit()
    process_due_work(db)
    return {"id": member.id, "floor": member.floor}


@router.get("/settings")
def read_settings(db: DbSession, _manager: Manager) -> dict:
    view = _settings_view(db)
    db.commit()
    return view


@router.put("/settings", dependencies=CSRF_DEPENDENCY)
def update_settings(payload: SettingsRequest, db: DbSession, _manager: Manager) -> dict:
    config = get_settings(db)
    for field, value in payload.model_dump().items():
        setattr(config, field, value)
    db.commit()
    process_due_work(db)
    return _settings_view(db)


@router.get("/offers")
def declined_and_expired_offers(
    db: DbSession, _manager: Manager, limit: int = Query(default=50, ge=1, le=200)
) -> list[dict]:
    process_due_work(db)
    rows = db.execute(
        select(TaskOffer, Task, Room, User.email)
        .join(Task, Task.id == TaskOffer.task_id)
        .join(Room, Room.id == Task.room_id)
        .join(User, User.id == TaskOffer.staff_id)
        .where(TaskOffer.status.in_((OfferStatus.DECLINED, OfferStatus.EXPIRED)))
        .order_by(TaskOffer.responded_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": offer.id,
            "task_id": task.id,
            "reference": reference(task),
            "room_number": room.number,
            "service": task.service.value,
            "staff": email,
            "outcome": offer.status.value,
            "responded_at": offer.responded_at.isoformat() if offer.responded_at else None,
            "task_status": task.status.value,
        }
        for offer, task, room, email in rows
    ]


@router.get("/rooms")
def room_readiness(db: DbSession, _manager: Manager) -> dict:
    rooms = db.scalars(select(Room).order_by(Room.floor, Room.number)).all()
    counts = dict(db.execute(select(Room.status, func.count(Room.id)).group_by(Room.status)).all())
    return {
        "summary": {state.value: counts.get(state, 0) for state in RoomStatus},
        "rooms": [
            {"id": room.id, "number": room.number, "floor": room.floor, "status": room.status.value}
            for room in rooms
        ],
    }


@router.post("/rooms/{room_id}/inspect", dependencies=CSRF_DEPENDENCY)
def mark_inspected(room_id: int, db: DbSession, _manager: Manager) -> dict:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.status != RoomStatus.AWAITING_INSPECTION:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only rooms awaiting inspection can be marked ready")
    room.status = RoomStatus.READY
    db.commit()
    return {"id": room.id, "status": room.status.value}


@router.post("/tasks/{task_id}/retry", dependencies=CSRF_DEPENDENCY)
def retry(task_id: int, db: DbSession, manager: Manager) -> dict[str, str]:
    task = _task(db, task_id)
    return _run(db, lambda: retry_task(db, task, manager))


@router.post("/tasks/{task_id}/assign", dependencies=CSRF_DEPENDENCY)
def assign(task_id: int, payload: AssignRequest, db: DbSession, manager: Manager) -> dict[str, str]:
    task = _task(db, task_id)
    staff = db.get(User, payload.staff_id)
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    return _run(db, lambda: assign_directly(db, task, staff, manager))


@router.post("/tasks/{task_id}/cancel", dependencies=CSRF_DEPENDENCY)
def cancel(task_id: int, db: DbSession, manager: Manager) -> dict[str, str]:
    task = _task(db, task_id)
    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed tasks cannot be cancelled")
    return _run(db, lambda: cancel_task(db, task, manager))
