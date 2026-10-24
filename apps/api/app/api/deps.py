from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_token, valid_csrf_token
from app.db.session import get_db
from app.models import AuthSession, User, UserRole, UserStatus

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


def require_administrator(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required"
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
Administrator = Annotated[User, Depends(require_administrator)]
