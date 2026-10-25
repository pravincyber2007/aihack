from enum import StrEnum

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(StrEnum):
    RECEPTIONIST = "receptionist"
    HOUSEKEEPING_MANAGER = "housekeeping_manager"
    HOUSEKEEPING_STAFF = "housekeeping_staff"


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole | None] = mapped_column(
        Enum(UserRole, native_enum=False, length=40), nullable=True
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, length=20),
        default=UserStatus.PENDING,
        nullable=False,
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Housekeeping staff only: the floor a manager allocated them to and whether
    # they are currently on shift and able to receive task offers.
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
