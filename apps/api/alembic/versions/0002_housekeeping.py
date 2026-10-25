"""Add rooms, guest stays, guest verification, tasks, and assignment settings.

Revision ID: 0002_housekeeping
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_housekeeping"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("users", sa.Column("floor", sa.Integer(), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(length=10), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
    )
    op.create_index("ix_rooms_number", "rooms", ["number"], unique=True)
    op.create_index("ix_rooms_floor", "rooms", ["floor"])

    op.create_table(
        "guest_stays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guest_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_in_at", TZ, nullable=False),
        sa.Column("check_out_at", TZ, nullable=False),
    )
    op.create_index("ix_guest_stays_phone", "guest_stays", ["phone"])

    op.create_table(
        "guest_otps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("stay_id", sa.Integer(), sa.ForeignKey("guest_stays.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("used_at", TZ, nullable=True),
    )
    op.create_index("ix_guest_otps_phone", "guest_otps", ["phone"])

    op.create_table(
        "guest_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("stay_id", sa.Integer(), sa.ForeignKey("guest_stays.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
    )
    op.create_index("ix_guest_sessions_token_hash", "guest_sessions", ["token_hash"], unique=True)
    op.create_index("ix_guest_sessions_stay_id", "guest_sessions", ["stay_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service", sa.String(length=30), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("guest_stay_id", sa.Integer(), sa.ForeignKey("guest_stays.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("alert_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
        sa.Column("due_at", TZ, nullable=False),
        sa.Column("round_started_at", TZ, nullable=False),
        sa.Column("accepted_at", TZ, nullable=True),
        sa.Column("started_at", TZ, nullable=True),
        sa.Column("completed_at", TZ, nullable=True),
        sa.UniqueConstraint("guest_stay_id", "client_request_id", name="uq_tasks_guest_request"),
    )
    op.create_index("ix_tasks_room_id", "tasks", ["room_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_guest_stay_id", "tasks", ["guest_stay_id"])
    op.create_index("ix_tasks_assigned_to_id", "tasks", ["assigned_to_id"])

    op.create_table(
        "task_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("offered_at", TZ, nullable=False),
        sa.Column("expires_at", TZ, nullable=False),
        sa.Column("responded_at", TZ, nullable=True),
    )
    op.create_index("ix_task_offers_task_id", "task_offers", ["task_id"])
    op.create_index("ix_task_offers_staff_id", "task_offers", ["staff_id"])
    op.create_index("ix_task_offers_status", "task_offers", ["status"])
    op.create_index("ix_task_offers_expires_at", "task_offers", ["expires_at"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.String(length=255), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", TZ, nullable=False),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])

    op.create_table(
        "assignment_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("adjacent_floor_range", sa.Integer(), nullable=False),
        sa.Column("max_offer_attempts", sa.Integer(), nullable=False),
        sa.Column("offer_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_active_tasks_per_staff", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("assignment_settings")
    op.drop_index("ix_task_events_task_id", table_name="task_events")
    op.drop_table("task_events")
    for index in ("expires_at", "status", "staff_id", "task_id"):
        op.drop_index(f"ix_task_offers_{index}", table_name="task_offers")
    op.drop_table("task_offers")
    for index in ("assigned_to_id", "guest_stay_id", "status", "room_id"):
        op.drop_index(f"ix_tasks_{index}", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_guest_sessions_stay_id", table_name="guest_sessions")
    op.drop_index("ix_guest_sessions_token_hash", table_name="guest_sessions")
    op.drop_table("guest_sessions")
    op.drop_index("ix_guest_otps_phone", table_name="guest_otps")
    op.drop_table("guest_otps")
    op.drop_index("ix_guest_stays_phone", table_name="guest_stays")
    op.drop_table("guest_stays")
    op.drop_index("ix_rooms_floor", table_name="rooms")
    op.drop_index("ix_rooms_number", table_name="rooms")
    op.drop_table("rooms")
    op.drop_column("users", "is_available")
    op.drop_column("users", "floor")
