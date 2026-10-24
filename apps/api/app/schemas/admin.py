from pydantic import BaseModel

from app.models.user import UserRole
from app.schemas.auth import UserResponse


class PendingUserResponse(UserResponse):
    pass


class AssignRoleRequest(BaseModel):
    role: UserRole
