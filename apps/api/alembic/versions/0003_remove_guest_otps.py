"""Remove one-time-code guest verification.

Revision ID: 0003_remove_guest_otps
Revises: 0002_housekeeping
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_remove_guest_otps"
down_revision = "0002_housekeeping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_guest_otps_phone", table_name="guest_otps")
    op.drop_table("guest_otps")


def downgrade() -> None:
    op.create_table(
        "guest_otps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("stay_id", sa.Integer(), sa.ForeignKey("guest_stays.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_guest_otps_phone", "guest_otps", ["phone"])
