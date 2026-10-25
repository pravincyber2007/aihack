from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import GUEST_COOKIE_NAME, CurrentStay, DbSession, require_csrf
from app.core.config import settings
from app.core.security import hash_token, new_token
from app.models import GuestSession, Room, ServiceType, Task, TaskSource
from app.services.assignment import as_utc, create_task, utcnow
from app.services.guest_access import (
    GuestAccessError,
    GuestLookupLimited,
    find_current_stay,
    normalize_phone,
)
from app.services.task_views import guest_views

router = APIRouter()
CSRF_DEPENDENCY = [Depends(require_csrf)]
GUEST_SESSION_MAX = timedelta(hours=12)


class PhoneRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=30)


class GuestServiceRequest(BaseModel):
    service: ServiceType
    instructions: str = Field(default="", max_length=500)
    client_request_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


def _phone(raw: str) -> str:
    try:
        return normalize_phone(raw)
    except GuestAccessError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None


def _room_view(db: DbSession, stay) -> dict:
    room = db.get(Room, stay.room_id)
    return {"room_number": room.number, "services": [service.value for service in ServiceType]}


@router.post("/access", dependencies=CSRF_DEPENDENCY)
def guest_access(
    payload: PhoneRequest, request: Request, response: Response, db: DbSession
) -> dict:
    try:
        client_key = request.client.host if request.client else "unknown"
        stay = find_current_stay(db, _phone(payload.phone), client_key)
    except GuestLookupLimited as error:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)) from None
    except GuestAccessError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    token = new_token()
    expires_at = min(as_utc(stay.check_out_at), utcnow() + GUEST_SESSION_MAX)
    db.add(GuestSession(token_hash=hash_token(token), stay_id=stay.id, expires_at=expires_at))
    db.commit()
    response.set_cookie(
        key=GUEST_COOKIE_NAME,
        value=token,
        max_age=int((expires_at - utcnow()).total_seconds()),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return _room_view(db, stay)


@router.get("/me")
def guest_me(db: DbSession, stay: CurrentStay) -> dict:
    return _room_view(db, stay)


@router.post("/logout", dependencies=CSRF_DEPENDENCY)
def guest_logout(request: Request, response: Response, db: DbSession) -> dict[str, str]:
    token = request.cookies.get(GUEST_COOKIE_NAME)
    if token:
        db.query(GuestSession).filter(GuestSession.token_hash == hash_token(token)).delete()
        db.commit()
    response.delete_cookie(GUEST_COOKIE_NAME, path="/", httponly=True, samesite="lax")
    return {"message": "Signed out"}


@router.get("/requests")
def my_requests(db: DbSession, stay: CurrentStay) -> list[dict]:
    tasks = db.scalars(
        select(Task).where(Task.guest_stay_id == stay.id).order_by(Task.created_at.desc())
    ).all()
    return guest_views(db, list(tasks))


@router.post("/requests", status_code=status.HTTP_201_CREATED, dependencies=CSRF_DEPENDENCY)
def submit_request(payload: GuestServiceRequest, db: DbSession, stay: CurrentStay) -> dict:
    existing = db.scalar(
        select(Task).where(
            Task.guest_stay_id == stay.id, Task.client_request_id == payload.client_request_id
        )
    )
    if existing is None:
        try:
            existing = create_task(
                db,
                room=db.get(Room, stay.room_id),
                service=payload.service,
                instructions=payload.instructions,
                source=TaskSource.GUEST,
                guest_stay_id=stay.id,
                client_request_id=payload.client_request_id,
            )
            db.commit()
        except IntegrityError:
            # A concurrent duplicate click won the race; return that request.
            db.rollback()
            existing = db.scalar(
                select(Task).where(
                    Task.guest_stay_id == stay.id,
                    Task.client_request_id == payload.client_request_id,
                )
            )
    return guest_views(db, [existing])[0]
