"""Role-appropriate task representations.

Guest names and phone numbers are never included in staff-facing views, and
guest views never include staff identities.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Room, ServiceType, Task, TaskStatus, User
from app.services.assignment import as_utc, utcnow

# Need at least this many recent completions of a service before estimating.
MIN_ETA_SAMPLES = 5
ETA_LOOKBACK = timedelta(days=30)

GUEST_STATUS_LABELS = {
    TaskStatus.SUBMITTED: "Submitted",
    TaskStatus.PENDING_ASSIGNMENT: "Pending Assignment",
    TaskStatus.OFFERED: "Pending Assignment",
    TaskStatus.ESCALATED: "Pending Assignment",
    TaskStatus.ACCEPTED: "Accepted",
    TaskStatus.IN_PROGRESS: "In Progress",
    TaskStatus.COMPLETED: "Completed",
    TaskStatus.CANCELLED: "Cancelled",
}


def reference(task: Task) -> str:
    return f"HK-{task.id:05d}"


def _iso(value: datetime | None) -> str | None:
    return as_utc(value).isoformat() if value else None


def is_overdue(task: Task) -> bool:
    return task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED) and as_utc(
        task.due_at
    ) < utcnow()


def average_durations(db: Session) -> dict[ServiceType, timedelta]:
    """Mean creation-to-completion time per service, only where data is sufficient."""
    since = utcnow() - ETA_LOOKBACK
    samples: dict[ServiceType, list[timedelta]] = {}
    for service, created, completed in db.execute(
        select(Task.service, Task.created_at, Task.completed_at).where(
            Task.status == TaskStatus.COMPLETED, Task.completed_at >= since
        )
    ):
        samples.setdefault(service, []).append(as_utc(completed) - as_utc(created))
    return {
        service: sum(values, timedelta()) / len(values)
        for service, values in samples.items()
        if len(values) >= MIN_ETA_SAMPLES
    }


def estimated_completion(task: Task, averages: dict[ServiceType, timedelta]) -> str | None:
    if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
        return None
    average = averages.get(task.service)
    if average is None:
        return None
    estimate = as_utc(task.created_at) + average
    # An estimate already in the past is not reliable; report none instead.
    return estimate.isoformat() if estimate > utcnow() else None


def _rooms(db: Session, tasks: list[Task]) -> dict[int, Room]:
    ids = {task.room_id for task in tasks}
    return {room.id: room for room in db.scalars(select(Room).where(Room.id.in_(ids)))} if ids else {}


def _users(db: Session, tasks: list[Task]) -> dict[int, User]:
    ids = {task.assigned_to_id for task in tasks if task.assigned_to_id}
    return {user.id: user for user in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


def _base(task: Task, room: Room) -> dict:
    return {
        "id": task.id,
        "reference": reference(task),
        "room_number": room.number,
        "floor": room.floor,
        "service": task.service.value,
        "priority": task.priority.value,
        "status": task.status.value,
        "instructions": task.instructions,
        "created_at": _iso(task.created_at),
        "due_at": _iso(task.due_at),
        "overdue": is_overdue(task),
    }


def staff_views(db: Session, tasks: list[Task]) -> list[dict]:
    rooms = _rooms(db, tasks)
    return [
        {**_base(t, rooms[t.room_id]), "accepted_at": _iso(t.accepted_at), "started_at": _iso(t.started_at),
         "completed_at": _iso(t.completed_at)}
        for t in tasks
    ]


def management_views(db: Session, tasks: list[Task]) -> list[dict]:
    rooms, users = _rooms(db, tasks), _users(db, tasks)
    return [
        {
            **_base(t, rooms[t.room_id]),
            "source": t.source.value,
            "assigned_to": users[t.assigned_to_id].email if t.assigned_to_id in users else None,
            "attempts": t.attempts,
            "alert_reason": t.alert_reason,
            "accepted_at": _iso(t.accepted_at),
            "started_at": _iso(t.started_at),
            "completed_at": _iso(t.completed_at),
        }
        for t in tasks
    ]


def reception_views(db: Session, tasks: list[Task]) -> list[dict]:
    rooms, averages = _rooms(db, tasks), average_durations(db)
    return [
        {
            **_base(t, rooms[t.room_id]),
            "source": t.source.value,
            "completed_at": _iso(t.completed_at),
            "estimated_completion_at": estimated_completion(t, averages),
        }
        for t in tasks
    ]


def guest_views(db: Session, tasks: list[Task]) -> list[dict]:
    averages = average_durations(db)
    return [
        {
            "id": t.id,
            "reference": reference(t),
            "service": t.service.value,
            "instructions": t.instructions,
            "status": GUEST_STATUS_LABELS[t.status],
            "created_at": _iso(t.created_at),
            "completed_at": _iso(t.completed_at),
            "estimated_completion_at": estimated_completion(t, averages),
        }
        for t in tasks
    ]
