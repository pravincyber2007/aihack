import logging
import smtplib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession, require_csrf
from app.core.config import settings
from app.core.security import hash_password, hash_token, new_token, verify_password
from app.models import AuthSession, EmailToken, User, UserStatus
from app.schemas.auth import (
    CsrfResponse,
    Credentials,
    EmailRequest,
    LoginRequest,
    MessageResponse,
    PasswordReset,
    Registration,
    TokenRequest,
    UserResponse,
)
from app.services.email import send_action_email

logger = logging.getLogger(__name__)
router = APIRouter()
CSRF_DEPENDENCY = [Depends(require_csrf)]
TOKEN_LIFETIME = timedelta(minutes=30)
DUMMY_PASSWORD_HASH = hash_password("staff-portal-dummy-password")
GENERIC_RESET_MESSAGE = (
    "If an account matches that email, instructions will be sent shortly."
)


def _create_email_token(db: Session, user: User, purpose: str) -> str:
    raw_token = new_token()
    db.add(
        EmailToken(
            token_hash=hash_token(raw_token),
            purpose=purpose,
            user_id=user.id,
            expires_at=datetime.now(UTC) + TOKEN_LIFETIME,
        )
    )
    return raw_token


def _send_email(*, recipient: str, subject: str, action_path: str, token: str) -> None:
    action_url = f"{settings.frontend_url.rstrip('/')}{action_path}?token={token}"
    try:
        send_action_email(recipient=recipient, subject=subject, action_url=action_url)
    except (OSError, RuntimeError, smtplib.SMTPException):
        logger.exception("Could not send %s email", subject)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is temporarily unavailable. Please try again later.",
        ) from None


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_lifetime_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _issue_session(db: Session, response: Response, user: User) -> None:
    token = new_token()
    db.add(
        AuthSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=datetime.now(UTC)
            + timedelta(hours=settings.session_lifetime_hours),
        )
    )
    db.commit()
    _set_session_cookie(response, token)


@router.get("/csrf", response_model=CsrfResponse)
def get_csrf_token(response: Response) -> CsrfResponse:
    token = new_token()
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=3600,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return CsrfResponse(csrf_token=token)


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=CSRF_DEPENDENCY,
)
def register(payload: Registration, db: DbSession) -> MessageResponse:
    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=None,
        status=UserStatus.PENDING,
        email_verified=False,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None

    token = _create_email_token(db, user, "verification")
    db.commit()
    _send_email(
        recipient=user.email,
        subject="Verify your staff portal email",
        action_path="/verify-email",
        token=token,
    )
    return MessageResponse(
        message="Check your email for a verification link. An administrator must approve your account."
    )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=CSRF_DEPENDENCY,
)
def verify_email(payload: TokenRequest, db: DbSession) -> MessageResponse:
    token = (
        db.query(EmailToken)
        .filter(
            EmailToken.token_hash == hash_token(payload.token),
            EmailToken.purpose == "verification",
            EmailToken.used_at.is_(None),
            EmailToken.expires_at > datetime.now(UTC),
        )
        .first()
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is invalid or expired",
        )
    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is invalid or expired",
        )
    token.used_at = datetime.now(UTC)
    user.email_verified = True
    db.commit()
    return MessageResponse(message="Email verified. An administrator must approve your account.")


@router.post(
    "/verification/resend",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=CSRF_DEPENDENCY,
)
def resend_verification(payload: EmailRequest, db: DbSession) -> MessageResponse:
    user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    if user and not user.email_verified:
        token = _create_email_token(db, user, "verification")
        db.commit()
        _send_email(
            recipient=user.email,
            subject="Verify your staff portal email",
            action_path="/verify-email",
            token=token,
        )
    return MessageResponse(
        message="If the address needs verification, a new link will be sent shortly."
    )


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=CSRF_DEPENDENCY,
)
def login(
    payload: LoginRequest, response: Response, db: DbSession
) -> UserResponse:
    user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    if not user:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
        )
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email before signing in",
        )
    if user.status != UserStatus.ACTIVE or user.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is waiting for administrator approval",
        )
    if payload.selected_role is not None and payload.selected_role != user.role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The selected role does not match your account",
        )
    _issue_session(db, response, user)
    return UserResponse.model_validate(user)


@router.post(
    "/refresh",
    response_model=UserResponse,
    dependencies=CSRF_DEPENDENCY,
)
def refresh_session(
    request: Request, response: Response, db: DbSession, user: CurrentUser
) -> UserResponse:
    current_token = request.cookies.get(settings.session_cookie_name)
    session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == hash_token(current_token or ""))
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        )
    token = new_token()
    session.token_hash = hash_token(token)
    session.expires_at = datetime.now(UTC) + timedelta(
        hours=settings.session_lifetime_hours
    )
    db.commit()
    _set_session_cookie(response, token)
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
def get_me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    dependencies=CSRF_DEPENDENCY,
)
def logout(request: Request, response: Response, db: DbSession) -> MessageResponse:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        db.query(AuthSession).filter(
            AuthSession.token_hash == hash_token(token)
        ).delete()
        db.commit()
    _clear_session_cookie(response)
    return MessageResponse(message="You have been signed out")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=CSRF_DEPENDENCY,
)
def forgot_password(payload: EmailRequest, db: DbSession) -> MessageResponse:
    user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    if user:
        token = _create_email_token(db, user, "password_reset")
        db.commit()
        _send_email(
            recipient=user.email,
            subject="Reset your staff portal password",
            action_path="/reset-password",
            token=token,
        )
    return MessageResponse(message=GENERIC_RESET_MESSAGE)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=CSRF_DEPENDENCY,
)
def reset_password(payload: PasswordReset, db: DbSession) -> MessageResponse:
    token = (
        db.query(EmailToken)
        .filter(
            EmailToken.token_hash == hash_token(payload.token),
            EmailToken.purpose == "password_reset",
            EmailToken.used_at.is_(None),
            EmailToken.expires_at > datetime.now(UTC),
        )
        .first()
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or expired",
        )

    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or expired",
        )
    now = datetime.now(UTC)
    token.used_at = now
    user.password_hash = hash_password(payload.password)
    db.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
    db.commit()
    return MessageResponse(message="Password updated. You can now sign in.")
