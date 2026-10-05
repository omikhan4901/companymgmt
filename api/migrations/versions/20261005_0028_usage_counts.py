"""usage counts for operators: aggregates only, across workspaces

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

from migrations import rls

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Like app_user_workspaces: a SELECT-only policy for the owner, used only by a
    # SECURITY DEFINER function that returns counts, never rows. The app role never gets it.
    op.execute("CREATE POLICY owner_read ON domain_events FOR SELECT TO current_user USING (true)")
    op.execute(
        """
        CREATE FUNCTION app_usage_counts(p_since timestamptz)
        RETURNS TABLE (name text, events bigint, workspaces bigint)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
        $$ SELECT e.name::text, count(*), count(DISTINCT e.tenant_id)
           FROM domain_events e
           WHERE e.occurred_at >= p_since
           GROUP BY e.name
           ORDER BY count(*) DESC $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION app_usage_counts(timestamptz) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION app_usage_counts(timestamptz) TO {rls.app_role()}")


def downgrade() -> None:
    op.execute("DROP FUNCTION app_usage_counts(timestamptz)")
    op.execute("DROP POLICY owner_read ON domain_events")
