from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.deps import DbSession, Receptionist, require_csrf
from app.models import GuestSession, GuestStay, Room, RoomStatus, ServiceType, Task, TaskSource
from app.services.assignment import OPEN_STATUSES, as_utc, create_task, process_due_work, utcnow
from app.services.guest_access import GuestAccessError, current_stays, normalize_phone
from app.services.task_views import reception_views

router = APIRouter()
CSRF_DEPENDENCY = [Depends(require_csrf)]
MAX_ROOMS_LISTED = 60


class ReceptionRequest(BaseModel):
    room_number: str = Field(min_length=1, max_length=10)
    service: ServiceType
    instructions: str = Field(default="", max_length=500)
    urgent: bool = False


class CheckInRequest(BaseModel):
    room_number: str = Field(min_length=1, max_length=10)
    guest_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=30)
    nights: int = Field(ge=1, le=60)

    @field_validator("guest_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter the guest's name")
        return value


class CheckOutRequest(BaseModel):
    room_number: str = Field(min_length=1, max_length=10)


def _room(db: DbSession, number: str) -> Room:
    room = db.scalar(select(Room).where(Room.number == number.strip()))
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


def _current_stays_by_room(db: DbSession, room_ids: list[int]) -> dict[int, GuestStay]:
    now = utcnow()
    stays = db.scalars(
        select(GuestStay).where(
            GuestStay.room_id.in_(room_ids),
            GuestStay.check_in_at <= now,
            GuestStay.check_out_at > now,
        )
    )
    return {stay.room_id: stay for stay in stays}


def _occupancy(stay: GuestStay | None) -> dict | None:
    # Only what the desk needs to recognise the guest: name, last 4 digits, departure.
    if stay is None:
        return None
    return {
        "guest_name": stay.guest_name,
        "phone_last4": stay.phone[-4:],
        "check_in_at": as_utc(stay.check_in_at).isoformat(),
        "check_out_at": as_utc(stay.check_out_at).isoformat(),
    }


def _room_views(db: DbSession, rooms: list[Room]) -> list[dict]:
    room_ids = [room.id for room in rooms]
    stays = _current_stays_by_room(db, room_ids)
    open_tasks = db.scalars(
        select(Task).where(Task.room_id.in_(room_ids), Task.status.in_(OPEN_STATUSES)).order_by(Task.created_at)
    ).all()
    views = reception_views(db, list(open_tasks))
    return [
        {
            "id": room.id,
            "number": room.number,
            "floor": room.floor,
            "status": room.status.value,
            "occupancy": _occupancy(stays.get(room.id)),
            "available": room.id not in stays and room.status == RoomStatus.READY,
            "open_requests": [view for view in views if view["room_number"] == room.number],
        }
        for room in rooms
    ]


@router.get("/rooms")
def search_rooms(
    db: DbSession,
    _user: Receptionist,
    query: str = Query(default="", max_length=10),
    occupancy: Literal["all", "available", "occupied"] = "all",
) -> list[dict]:
    process_due_work(db)
    statement = select(Room).order_by(Room.floor, Room.number)
    if query.strip():
        statement = statement.where(Room.number.startswith(query.strip()))
    views = _room_views(db, list(db.scalars(statement)))
    if occupancy == "available":
        views = [view for view in views if view["available"]]
    elif occupancy == "occupied":
        views = [view for view in views if view["occupancy"]]
    return views[:MAX_ROOMS_LISTED]


@router.get("/summary")
def occupancy_summary(db: DbSession, _user: Receptionist) -> dict[str, int]:
    rooms = list(db.scalars(select(Room)))
    occupied = _current_stays_by_room(db, [room.id for room in rooms])
    return {
        "total": len(rooms),
        "occupied": len(occupied),
        "available": sum(1 for r in rooms if r.id not in occupied and r.status == RoomStatus.READY),
        "needs_cleaning": sum(1 for r in rooms if r.status != RoomStatus.READY),
    }


@router.post("/check-in", status_code=status.HTTP_201_CREATED, dependencies=CSRF_DEPENDENCY)
def check_in(payload: CheckInRequest, db: DbSession, _user: Receptionist) -> dict:
    room = _room(db, payload.room_number)
    try:
        phone = normalize_phone(payload.phone)
    except GuestAccessError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    if _current_stays_by_room(db, [room.id]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Room {room.number} already has a guest checked in")
    if room.status != RoomStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room {room.number} is not ready yet. Choose a room marked Ready.",
        )
    # One current stay per phone number keeps guest access unambiguous.
    existing = current_stays(db, phone)
    if existing:
        other = db.get(Room, existing[0].room_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This phone number is already checked in to room {other.number}. Check that guest out first.",
        )
    now = utcnow()
    stay = GuestStay(
        guest_name=payload.guest_name,
        phone=phone,
        room_id=room.id,
        check_in_at=now,
        check_out_at=now + timedelta(days=payload.nights),
    )
    db.add(stay)
    db.commit()
    return _room_views(db, [room])[0]


@router.post("/check-out", dependencies=CSRF_DEPENDENCY)
def check_out(payload: CheckOutRequest, db: DbSession, user: Receptionist) -> dict:
    room = _room(db, payload.room_number)
    stay = _current_stays_by_room(db, [room.id]).get(room.id)
    if stay is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Room {room.number} has no guest checked in")
    stay.check_out_at = utcnow()
    db.query(GuestSession).filter(GuestSession.stay_id == stay.id).delete()
    # The room needs a full clean before the next guest; housekeeping is assigned automatically.
    room.status = RoomStatus.CLEANING_REQUIRED
    create_task(
        db,
        room=room,
        service=ServiceType.CLEANING,
        instructions="Checkout clean - prepare room for the next guest",
        source=TaskSource.RECEPTION,
        created_by_id=user.id,
    )
    db.commit()
    return _room_views(db, [room])[0]


@router.get("/requests")
def recent_requests(db: DbSession, _user: Receptionist) -> list[dict]:
    process_due_work(db)
    tasks = db.scalars(select(Task).order_by(Task.created_at.desc()).limit(50)).all()
    return reception_views(db, list(tasks))


@router.post("/requests", status_code=status.HTTP_201_CREATED, dependencies=CSRF_DEPENDENCY)
def submit_request(payload: ReceptionRequest, db: DbSession, user: Receptionist) -> dict:
    room = _room(db, payload.room_number)
    task = create_task(
        db,
        room=room,
        service=payload.service,
        instructions=payload.instructions,
        source=TaskSource.RECEPTION,
        urgent=payload.urgent,
        created_by_id=user.id,
    )
    db.commit()
    return reception_views(db, [task])[0]
