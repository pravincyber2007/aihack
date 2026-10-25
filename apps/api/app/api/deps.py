from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_token, valid_csrf_token
from app.db.session import get_db
from app.models import AuthSession, GuestSession, GuestStay, User, UserRole, UserStatus
from app.services.assignment import as_utc

DbSession = Annotated[Session, Depends(get_db)]


def require_csrf(request: Request) -> None:
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get("X-CSRF-Token")
    if not valid_csrf_token(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token"
        )


def get_current_user(request: Request, db: DbSession) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    session = (
        db.query(AuthSession)
        .filter(
            AuthSession.token_hash == hash_token(token),
            AuthSession.expires_at > datetime.now(UTC),
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        )

    user = db.get(User, session.user_id)
    if not user or user.status != UserStatus.ACTIVE or user.role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not active"
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """Dependency enforcing that the signed-in user holds one of the given roles."""

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return user

    return checker


Manager = Annotated[User, Depends(require_roles(UserRole.HOUSEKEEPING_MANAGER))]
Staff = Annotated[User, Depends(require_roles(UserRole.HOUSEKEEPING_STAFF))]
Receptionist = Annotated[User, Depends(require_roles(UserRole.RECEPTIONIST))]

GUEST_COOKIE_NAME = "guest_session"


def get_current_stay(request: Request, db: DbSession) -> GuestStay:
    token = request.cookies.get(GUEST_COOKIE_NAME)
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Please enter your registered phone number"
    )
    if not token:
        raise unauthorized
    now = datetime.now(UTC)
    session = db.scalar(
        select(GuestSession).where(
            GuestSession.token_hash == hash_token(token), GuestSession.expires_at > now
        )
    )
    stay = db.get(GuestStay, session.stay_id) if session else None
    if stay is None or not (as_utc(stay.check_in_at) <= now < as_utc(stay.check_out_at)):
        raise unauthorized
    return stay


CurrentStay = Annotated[GuestStay, Depends(get_current_stay)]
