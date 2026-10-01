"""lateness: when the working day starts, and the grace period before a clock-in is late

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-01 13:03:39.677165
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attendance_settings",
        sa.Column("day_starts_at", sa.Time(), server_default=sa.text("'09:00'"), nullable=False),
    )
    op.add_column(
        "attendance_settings",
        sa.Column("late_after_minutes", sa.SmallInteger(), server_default=sa.text("15"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_attendance_settings_late_after"),
        "attendance_settings",
        "late_after_minutes BETWEEN 0 AND 240",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_attendance_settings_late_after"), "attendance_settings", type_="check")
    op.drop_column("attendance_settings", "late_after_minutes")
    op.drop_column("attendance_settings", "day_starts_at")
