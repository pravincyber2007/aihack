"""Automatic housekeeping task assignment.

Every new request is offered to one eligible staff member at a time. Candidates
are housekeeping staff who are active, on shift, allocated to the room's floor
or a permitted adjacent floor, and below the active-task limit. They are ranked
by floor distance, then current workload. Declined and expired offers trigger
another offer until the attempt limit is reached, at which point the task is
escalated to the housekeeping manager.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    AssignmentSettings,
    OfferStatus,
    Room,
    RoomStatus,
    ServiceType,
    Task,
    TaskEvent,
    TaskOffer,
    TaskPriority,
    TaskSource,
    TaskStatus,
    User,
    UserRole,
    UserStatus,
)

# Priority rules: a base priority per service, raised by the conditions in
# calculate_priority. Shown to managers so the rules are not a black box.
BASE_PRIORITY: dict[ServiceType, TaskPriority] = {
    ServiceType.CLEANING: TaskPriority.NORMAL,
    ServiceType.TOWELS: TaskPriority.NORMAL,
    ServiceType.TOILETRIES: TaskPriority.LOW,
    ServiceType.WATER: TaskPriority.NORMAL,
    ServiceType.PILLOWS: TaskPriority.LOW,
    ServiceType.ISSUE: TaskPriority.HIGH,
    ServiceType.OTHER: TaskPriority.NORMAL,
}
PRIORITY_ORDER = [TaskPriority.LOW, TaskPriority.NORMAL, TaskPriority.HIGH, TaskPriority.URGENT]
# Minutes from creation until a task counts as overdue.
TARGET_MINUTES: dict[TaskPriority, int] = {
    TaskPriority.URGENT: 20,
    TaskPriority.HIGH: 45,
    TaskPriority.NORMAL: 90,
    TaskPriority.LOW: 180,
}
PRIORITY_RULES = [
    "Each service has a base priority (room issues start high; toiletries and pillows start low).",
    "A receptionist can mark a request as urgent.",
    "A request is raised one level when the same room already has another open request.",
    "Overdue targets: urgent 20 min, high 45 min, normal 90 min, low 180 min.",
]
OPEN_STATUSES = (
    TaskStatus.SUBMITTED,
    TaskStatus.PENDING_ASSIGNMENT,
    TaskStatus.OFFERED,
    TaskStatus.ACCEPTED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.ESCALATED,
)
ACTIVE_WORK_STATUSES = (TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS)


class AssignmentError(Exception):
    """Raised when a staff action conflicts with the task's current state."""


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    # SQLite (used in tests) returns naive datetimes; PostgreSQL returns aware ones.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def get_settings(db: Session) -> AssignmentSettings:
    settings = db.get(AssignmentSettings, 1)
    if settings is None:
        settings = AssignmentSettings(
            id=1,
            adjacent_floor_range=1,
            max_offer_attempts=3,
            offer_timeout_seconds=120,
            max_active_tasks_per_staff=3,
        )
        db.add(settings)
        db.flush()
    return settings


def log_event(
    db: Session, task: Task, event: str, detail: str = "", actor_id: int | None = None
) -> None:
    db.add(
        TaskEvent(task_id=task.id, event=event, detail=detail, actor_id=actor_id, created_at=utcnow())
    )


def calculate_priority(
    db: Session, room: Room, service: ServiceType, urgent: bool = False
) -> TaskPriority:
    if urgent:
        return TaskPriority.URGENT
    priority = BASE_PRIORITY[service]
    open_for_room = db.scalar(
        select(func.count(Task.id)).where(Task.room_id == room.id, Task.status.in_(OPEN_STATUSES))
    )
    if open_for_room:
        priority = PRIORITY_ORDER[min(PRIORITY_ORDER.index(priority) + 1, len(PRIORITY_ORDER) - 1)]
    return priority


def create_task(
    db: Session,
    *,
    room: Room,
    service: ServiceType,
    instructions: str,
    source: TaskSource,
    urgent: bool = False,
    guest_stay_id: int | None = None,
    client_request_id: str | None = None,
    created_by_id: int | None = None,
) -> Task:
    now = utcnow()
    priority = calculate_priority(db, room, service, urgent)
    task = Task(
        room_id=room.id,
        service=service,
        instructions=instructions.strip(),
        priority=priority,
        status=TaskStatus.SUBMITTED,
        source=source,
        guest_stay_id=guest_stay_id,
        client_request_id=client_request_id,
        created_by_id=created_by_id,
        attempts=0,
        created_at=now,
        due_at=now + timedelta(minutes=TARGET_MINUTES[priority]),
        round_started_at=now,
    )
    db.add(task)
    db.flush()
    log_event(db, task, "created", f"{source.value} request, priority {priority.value}", created_by_id)
    if service == ServiceType.CLEANING and room.status == RoomStatus.READY:
        room.status = RoomStatus.CLEANING_REQUIRED
    dispatch(db, task)
    return task


def staff_workload(db: Session, staff_ids: list[int]) -> dict[int, int]:
    """Active tasks plus outstanding offers for each staff member."""
    if not staff_ids:
        return {}
    workload = dict.fromkeys(staff_ids, 0)
    for staff_id, count in db.execute(
        select(Task.assigned_to_id, func.count(Task.id))
        .where(Task.assigned_to_id.in_(staff_ids), Task.status.in_(ACTIVE_WORK_STATUSES))
        .group_by(Task.assigned_to_id)
    ):
        workload[staff_id] += count
    for staff_id, count in db.execute(
        select(TaskOffer.staff_id, func.count(TaskOffer.id))
        .where(TaskOffer.staff_id.in_(staff_ids), TaskOffer.status == OfferStatus.PENDING)
        .group_by(TaskOffer.staff_id)
    ):
        workload[staff_id] += count
    return workload


def _escalate(db: Session, task: Task, reason: str) -> None:
    task.status = TaskStatus.ESCALATED
    task.alert_reason = reason
    log_event(db, task, "escalated", reason)


def dispatch(db: Session, task: Task) -> None:
    """Offer the task to the best eligible staff member, or raise an alert."""
    if task.status not in (TaskStatus.SUBMITTED, TaskStatus.PENDING_ASSIGNMENT):
        return
    if db.scalar(
        select(TaskOffer.id).where(TaskOffer.task_id == task.id, TaskOffer.status == OfferStatus.PENDING)
    ):
        return

    config = get_settings(db)
    if task.attempts >= config.max_offer_attempts:
        _escalate(db, task, f"No one accepted after {task.attempts} offers")
        return

    room = db.get(Room, task.room_id)
    already_tried = select(TaskOffer.staff_id).where(
        TaskOffer.task_id == task.id,
        TaskOffer.offered_at >= task.round_started_at,
        TaskOffer.status.in_((OfferStatus.DECLINED, OfferStatus.EXPIRED)),
    )
    staff = db.scalars(
        select(User).where(
            User.role == UserRole.HOUSEKEEPING_STAFF,
            User.status == UserStatus.ACTIVE,
            User.is_available.is_(True),
            User.floor.is_not(None),
            func.abs(User.floor - room.floor) <= config.adjacent_floor_range,
            User.id.not_in(already_tried),
        )
    ).all()
    workload = staff_workload(db, [member.id for member in staff])
    candidates = sorted(
        (m for m in staff if workload[m.id] < config.max_active_tasks_per_staff),
        key=lambda m: (abs(m.floor - room.floor), workload[m.id], m.id),
    )

    if not candidates:
        reason = (
            f"No available staff on floor {room.floor}"
            + (f" or within {config.adjacent_floor_range} adjacent floor(s)" if config.adjacent_floor_range else "")
        )
        if task.status != TaskStatus.PENDING_ASSIGNMENT or task.alert_reason != reason:
            log_event(db, task, "unassignable", reason)
        task.status = TaskStatus.PENDING_ASSIGNMENT
        task.alert_reason = reason
        return

    chosen = candidates[0]
    now = utcnow()
    db.add(
        TaskOffer(
            task_id=task.id,
            staff_id=chosen.id,
            status=OfferStatus.PENDING,
            offered_at=now,
            expires_at=now + timedelta(seconds=config.offer_timeout_seconds),
        )
    )
    task.status = TaskStatus.OFFERED
    task.alert_reason = None
    task.attempts += 1
    log_event(db, task, "offered", f"Offered to {chosen.email} (floor {chosen.floor})")


def _locked_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id, with_for_update=True)
    if task is None:
        raise AssignmentError("Task not found")
    return task


def _close_offer(db: Session, offer: TaskOffer, status: OfferStatus) -> bool:
    """Atomically move a pending offer to its final state; False if already closed."""
    result = db.execute(
        update(TaskOffer)
        .where(TaskOffer.id == offer.id, TaskOffer.status == OfferStatus.PENDING)
        .values(status=status, responded_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    db.refresh(offer)
    return result.rowcount == 1


def accept_offer(db: Session, offer: TaskOffer, staff: User) -> Task:
    if offer.staff_id != staff.id:
        raise AssignmentError("Offer not found")
    task = _locked_task(db, offer.task_id)
    if offer.status != OfferStatus.PENDING or as_utc(offer.expires_at) <= utcnow():
        raise AssignmentError("This offer is no longer available")
    # Conditional update: only one staff member can ever become the owner.
    claimed = db.execute(
        update(Task)
        .where(Task.id == task.id, Task.status == TaskStatus.OFFERED, Task.assigned_to_id.is_(None))
        .values(status=TaskStatus.ACCEPTED, assigned_to_id=staff.id, accepted_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1 or not _close_offer(db, offer, OfferStatus.ACCEPTED):
        db.rollback()
        raise AssignmentError("This task has already been taken")
    db.refresh(task)
    log_event(db, task, "accepted", f"Accepted by {staff.email}", staff.id)
    return task


def decline_offer(db: Session, offer: TaskOffer, staff: User) -> None:
    if offer.staff_id != staff.id:
        raise AssignmentError("Offer not found")
    task = _locked_task(db, offer.task_id)
    if not _close_offer(db, offer, OfferStatus.DECLINED):
        raise AssignmentError("This offer is no longer available")
    log_event(db, task, "declined", f"Declined by {staff.email}", staff.id)
    if task.status == TaskStatus.OFFERED:
        task.status = TaskStatus.PENDING_ASSIGNMENT
        dispatch(db, task)


def process_due_work(db: Session) -> None:
    """Expire overdue offers and retry tasks still waiting for staff."""
    now = utcnow()
    expired = db.scalars(
        select(TaskOffer).where(TaskOffer.status == OfferStatus.PENDING, TaskOffer.expires_at <= now)
    ).all()
    for offer in expired:
        task = _locked_task(db, offer.task_id)
        if _close_offer(db, offer, OfferStatus.EXPIRED):
            staff = db.get(User, offer.staff_id)
            log_event(db, task, "timed_out", f"No response from {staff.email if staff else 'staff'}")
            if task.status == TaskStatus.OFFERED:
                task.status = TaskStatus.PENDING_ASSIGNMENT
                dispatch(db, task)
    for task in db.scalars(select(Task).where(Task.status == TaskStatus.PENDING_ASSIGNMENT)).all():
        dispatch(db, task)
    db.commit()


def retry_task(db: Session, task: Task, actor: User) -> None:
    if task.status not in (TaskStatus.ESCALATED, TaskStatus.PENDING_ASSIGNMENT):
        raise AssignmentError("Only unassigned tasks can be retried")
    now = utcnow()
    task.status = TaskStatus.PENDING_ASSIGNMENT
    task.attempts = 0
    task.round_started_at = now
    log_event(db, task, "retried", "Automatic assignment restarted by manager", actor.id)
    dispatch(db, task)


def assign_directly(db: Session, task: Task, staff: User, actor: User) -> None:
    if task.status not in (TaskStatus.ESCALATED, TaskStatus.PENDING_ASSIGNMENT, TaskStatus.OFFERED):
        raise AssignmentError("This task is already assigned or closed")
    if staff.role != UserRole.HOUSEKEEPING_STAFF or staff.status != UserStatus.ACTIVE:
        raise AssignmentError("Choose an active housekeeping staff member")
    for offer in db.scalars(
        select(TaskOffer).where(TaskOffer.task_id == task.id, TaskOffer.status == OfferStatus.PENDING)
    ):
        _close_offer(db, offer, OfferStatus.CANCELLED)
    task.status = TaskStatus.ACCEPTED
    task.assigned_to_id = staff.id
    task.accepted_at = utcnow()
    task.alert_reason = None
    log_event(db, task, "assigned", f"Assigned to {staff.email} by manager", actor.id)


def cancel_task(db: Session, task: Task, actor: User) -> None:
    if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
        raise AssignmentError("This task is already closed")
    for offer in db.scalars(
        select(TaskOffer).where(TaskOffer.task_id == task.id, TaskOffer.status == OfferStatus.PENDING)
    ):
        _close_offer(db, offer, OfferStatus.CANCELLED)
    task.status = TaskStatus.CANCELLED
    task.alert_reason = None
    log_event(db, task, "cancelled", "Cancelled by manager", actor.id)


def start_task(db: Session, task: Task, staff: User) -> None:
    if task.assigned_to_id != staff.id:
        raise AssignmentError("Task not found")
    if task.status != TaskStatus.ACCEPTED:
        raise AssignmentError("Only accepted tasks can be started")
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = utcnow()
    room = db.get(Room, task.room_id)
    if task.service == ServiceType.CLEANING:
        room.status = RoomStatus.CLEANING_IN_PROGRESS
    log_event(db, task, "started", f"Started by {staff.email}", staff.id)


def complete_task(db: Session, task: Task, staff: User) -> None:
    if task.assigned_to_id != staff.id:
        raise AssignmentError("Task not found")
    if task.status != TaskStatus.IN_PROGRESS:
        raise AssignmentError("Start the task before completing it")
    task.status = TaskStatus.COMPLETED
    task.completed_at = utcnow()
    room = db.get(Room, task.room_id)
    if task.service == ServiceType.CLEANING:
        room.status = RoomStatus.AWAITING_INSPECTION
    log_event(db, task, "completed", f"Completed by {staff.email}", staff.id)
