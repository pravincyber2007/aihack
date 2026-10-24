from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import Administrator, DbSession, require_csrf
from app.models import AuthSession, User, UserRole, UserStatus
from app.schemas.admin import AssignRoleRequest
from app.schemas.auth import UserResponse

router = APIRouter()


@router.get("/users/pending", response_model=list[UserResponse])
def list_pending_users(db: DbSession, _administrator: Administrator) -> list[UserResponse]:
    users = (
        db.query(User)
        .filter(User.status == UserStatus.PENDING, User.email_verified.is_(True))
        .order_by(User.id)
        .all()
    )
    return [UserResponse.model_validate(user) for user in users]


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    dependencies=[Depends(require_csrf)],
)
def assign_role(
    user_id: int,
    payload: AssignRoleRequest,
    db: DbSession,
    administrator: Administrator,
) -> UserResponse:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The account must verify its email before activation",
        )
    if user.status == UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disabled accounts cannot be activated through role assignment",
        )
    if user.id == administrator.id and payload.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrators cannot remove their own administrator role",
        )

    user.role = payload.role
    user.status = UserStatus.ACTIVE
    db.query(AuthSession).filter(AuthSession.user_id == user.id).delete()
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
