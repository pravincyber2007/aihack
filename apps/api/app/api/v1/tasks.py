from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import DbSession, Manager
from app.models import Task, TaskEvent, TaskStatus, User
from app.services.assignment import process_due_work
from app.services.task_views import management_views, reference

router = APIRouter()
ALERT_STATUSES = (TaskStatus.PENDING_ASSIGNMENT, TaskStatus.ESCALATED)


@router.get("")
def list_tasks(
    db: DbSession,
    _user: Manager,
    status_filter: list[TaskStatus] | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict]:
    process_due_work(db)
    query = select(Task).order_by(Task.created_at.desc()).limit(limit)
    if status_filter:
        query = query.where(Task.status.in_(status_filter))
    return management_views(db, list(db.scalars(query)))


@router.get("/summary")
def task_summary(db: DbSession, _user: Manager) -> dict[str, int]:
    process_due_work(db)
    counts = dict(db.execute(select(Task.status, func.count(Task.id)).group_by(Task.status)).all())
    return {state.value: counts.get(state, 0) for state in TaskStatus}


@router.get("/alerts")
def task_alerts(db: DbSession, _user: Manager) -> list[dict]:
    process_due_work(db)
    tasks = db.scalars(
        select(Task).where(Task.status.in_(ALERT_STATUSES)).order_by(Task.created_at)
    ).all()
    return management_views(db, list(tasks))


@router.get("/{task_id}/history")
def task_history(task_id: int, db: DbSession, _user: Manager) -> dict:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    rows = db.execute(
        select(TaskEvent, User.email)
        .outerjoin(User, User.id == TaskEvent.actor_id)
        .where(TaskEvent.task_id == task_id)
        .order_by(TaskEvent.created_at, TaskEvent.id)
    ).all()
    return {
        "reference": reference(task),
        "events": [
            {
                "event": event.event,
                "detail": event.detail,
                "actor": email,
                "created_at": event.created_at.isoformat(),
            }
            for event, email in rows
        ],
    }
