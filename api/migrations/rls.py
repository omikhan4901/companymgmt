"""Helpers every migration uses to protect tables.

- `tenant_table`: forced row-level security with one policy tied to `app.tenant_id`, and
  read/write grants for the app role.
- `global_table`: no RLS; explicit grants only.
- `append_only`: the app role may insert and read, never update or delete, and a trigger
  blocks changes even from the owner.
"""

from __future__ import annotations

import re

from alembic import op

from app.core.config import get_settings

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"Unsafe identifier: {name}")
    return name


def app_role() -> str:
    return _ident(get_settings().app_db_role)


def install_functions() -> None:
    role = app_role()
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_tenant() RETURNS uuid
        LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_forbid_change() RETURNS trigger
        LANGUAGE plpgsql AS
        $$ BEGIN
          -- Retention purges run as the owner role with app.allow_purge set; the app
          -- role has no DELETE grant at all.
          IF TG_OP IN ('DELETE', 'TRUNCATE')
             AND current_setting('app.allow_purge', true) = 'on' THEN
            RETURN OLD;
          END IF;
          RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = '42501';
        END $$
        """
    )


def tenant_table(table: str, *, privileges: str = "SELECT, INSERT, UPDATE, DELETE") -> None:
    t = _ident(table)
    op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {t} "
        "USING (tenant_id = app_current_tenant()) "
        "WITH CHECK (tenant_id = app_current_tenant())"
    )
    op.execute(f"GRANT {privileges} ON {t} TO {app_role()}")


def global_table(table: str, *, privileges: str = "SELECT, INSERT, UPDATE, DELETE") -> None:
    op.execute(f"GRANT {privileges} ON {_ident(table)} TO {app_role()}")


def append_only(table: str) -> None:
    t = _ident(table)
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {t} FROM {app_role()}")
    op.execute(
        f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
        "FOR EACH ROW EXECUTE FUNCTION app_forbid_change()"
    )
    op.execute(
        f"CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} "
        "FOR EACH STATEMENT EXECUTE FUNCTION app_forbid_change()"
    )
