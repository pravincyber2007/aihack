from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RoomStatus(StrEnum):
    CLEANING_REQUIRED = "cleaning_required"
    CLEANING_IN_PROGRESS = "cleaning_in_progress"
    AWAITING_INSPECTION = "awaiting_inspection"
    READY = "ready"


class ServiceType(StrEnum):
    CLEANING = "cleaning"
    TOWELS = "towels"
    TOILETRIES = "toiletries"
    WATER = "water"
    PILLOWS = "pillows"
    ISSUE = "issue"
    OTHER = "other"


class TaskPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(StrEnum):
    SUBMITTED = "submitted"
    PENDING_ASSIGNMENT = "pending_assignment"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class TaskSource(StrEnum):
    GUEST = "guest"
    RECEPTION = "reception"


class OfferStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def _enum(enum_type: type[StrEnum], length: int = 30) -> Enum:
    return Enum(enum_type, native_enum=False, length=length)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    floor: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[RoomStatus] = mapped_column(
        _enum(RoomStatus), default=RoomStatus.READY, nullable=False
    )


class GuestStay(Base):
    """A reservation for a guest who is (or will be) staying in a room."""

    __tablename__ = "guest_stays"

    id: Mapped[int] = mapped_column(primary_key=True)
    guest_name: Mapped[str] = mapped_column(String(120))
    # Digits only, so lookups do not depend on how the number was typed.
    phone: Mapped[str] = mapped_column(String(20), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GuestSession(Base):
    __tablename__ = "guest_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    stay_id: Mapped[int] = mapped_column(
        ForeignKey("guest_stays.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("guest_stay_id", "client_request_id", name="uq_tasks_guest_request"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    service: Mapped[ServiceType] = mapped_column(_enum(ServiceType))
    instructions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(_enum(TaskPriority))
    status: Mapped[TaskStatus] = mapped_column(_enum(TaskStatus), index=True)
    source: Mapped[TaskSource] = mapped_column(_enum(TaskSource))
    guest_stay_id: Mapped[int | None] = mapped_column(
        ForeignKey("guest_stays.id", ondelete="SET NULL"), index=True
    )
    # Lets a guest's repeated clicks resolve to the same request instead of duplicates.
    client_request_id: Mapped[str | None] = mapped_column(String(64))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alert_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    round_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskOffer(Base):
    __tablename__ = "task_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[OfferStatus] = mapped_column(_enum(OfferStatus), index=True)
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AssignmentSettings(Base):
    """Single-row table holding the manager-configurable assignment rules."""

    __tablename__ = "assignment_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    adjacent_floor_range: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_offer_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    offer_timeout_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    max_active_tasks_per_staff: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
