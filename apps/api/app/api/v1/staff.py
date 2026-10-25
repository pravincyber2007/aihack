from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.api.deps import DbSession, Staff, require_csrf
from app.models import OfferStatus, Task, TaskOffer, TaskStatus
from app.services.assignment import (
    AssignmentError,
    accept_offer,
    as_utc,
    complete_task,
    decline_offer,
    process_due_work,
    start_task,
    utcnow,
)
from app.services.task_views import staff_views

router = APIRouter()
CSRF_DEPENDENCY = [Depends(require_csrf)]


class AvailabilityRequest(BaseModel):
    is_available: bool


def _conflict(db: DbSession, error: AssignmentError) -> HTTPException:
    db.rollback()
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


def _own_offer(db: DbSession, offer_id: int, staff_id: int) -> TaskOffer:
    offer = db.get(TaskOffer, offer_id)
    # Another person's offer is reported as missing so its existence is not revealed.
    if offer is None or offer.staff_id != staff_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return offer


def _own_task(db: DbSession, task_id: int, staff_id: int) -> Task:
    task = db.get(Task, task_id, with_for_update=True)
    if task is None or task.assigned_to_id != staff_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("/me")
def my_shift(staff: Staff) -> dict:
    return {"floor": staff.floor, "is_available": staff.is_available}


@router.patch("/me", dependencies=CSRF_DEPENDENCY)
def set_availability(payload: AvailabilityRequest, db: DbSession, staff: Staff) -> dict:
    staff.is_available = payload.is_available
    db.commit()
    process_due_work(db)
    return {"floor": staff.floor, "is_available": staff.is_available}


@router.get("/offers")
def my_offers(db: DbSession, staff: Staff) -> list[dict]:
    process_due_work(db)
    offers = db.scalars(
        select(TaskOffer)
        .where(TaskOffer.staff_id == staff.id, TaskOffer.status == OfferStatus.PENDING)
        .order_by(TaskOffer.offered_at)
    ).all()
    tasks = {task.id: task for task in db.scalars(select(Task).where(Task.id.in_([o.task_id for o in offers])))}
    views = {view["id"]: view for view in staff_views(db, list(tasks.values()))}
    return [
        {"offer_id": offer.id, "expires_at": as_utc(offer.expires_at).isoformat(), "task": views[offer.task_id]}
        for offer in offers
    ]


@router.post("/offers/{offer_id}/accept", dependencies=CSRF_DEPENDENCY)
def accept(offer_id: int, db: DbSession, staff: Staff) -> dict:
    offer = _own_offer(db, offer_id, staff.id)
    try:
        task = accept_offer(db, offer, staff)
    except AssignmentError as error:
        raise _conflict(db, error) from None
    db.commit()
    return staff_views(db, [task])[0]


@router.post("/offers/{offer_id}/decline", dependencies=CSRF_DEPENDENCY)
def decline(offer_id: int, db: DbSession, staff: Staff) -> dict[str, str]:
    offer = _own_offer(db, offer_id, staff.id)
    try:
        decline_offer(db, offer, staff)
    except AssignmentError as error:
        raise _conflict(db, error) from None
    db.commit()
    return {"message": "Offer declined"}


@router.get("/tasks")
def my_tasks(db: DbSession, staff: Staff) -> list[dict]:
    since = utcnow() - timedelta(hours=24)
    tasks = db.scalars(
        select(Task)
        .where(
            Task.assigned_to_id == staff.id,
            or_(
                Task.status.in_((TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS)),
                (Task.status == TaskStatus.COMPLETED) & (Task.completed_at >= since),
            ),
        )
        .order_by(Task.due_at)
    ).all()
    return staff_views(db, list(tasks))


@router.post("/tasks/{task_id}/start", dependencies=CSRF_DEPENDENCY)
def start(task_id: int, db: DbSession, staff: Staff) -> dict:
    task = _own_task(db, task_id, staff.id)
    try:
        start_task(db, task, staff)
    except AssignmentError as error:
        raise _conflict(db, error) from None
    db.commit()
    return staff_views(db, [task])[0]


@router.post("/tasks/{task_id}/complete", dependencies=CSRF_DEPENDENCY)
def complete(task_id: int, db: DbSession, staff: Staff) -> dict:
    task = _own_task(db, task_id, staff.id)
    try:
        complete_task(db, task, staff)
    except AssignmentError as error:
        raise _conflict(db, error) from None
    db.commit()
    return staff_views(db, [task])[0]
