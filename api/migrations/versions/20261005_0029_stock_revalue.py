"""stock movements: 'revalue' for stock sold before its delivery was recorded

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "'opening', 'purchase', 'sale', 'return', 'void', 'adjustment', 'count', 'transfer_out', 'transfer_in'"
)


def upgrade() -> None:
    op.drop_constraint(op.f("ck_stock_movements_kind"), "stock_movements", type_="check")
    op.create_check_constraint("kind", "stock_movements", f"kind IN ({KINDS}, 'revalue')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_stock_movements_kind"), "stock_movements", type_="check")
    op.create_check_constraint("kind", "stock_movements", f"kind IN ({KINDS})")
