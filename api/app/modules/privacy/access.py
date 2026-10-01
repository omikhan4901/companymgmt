"""Privacy permissions."""

from app.core import permissions as perms

WORKSPACE_EXPORT = perms.register(
    "workspace.export", "Export all of the workspace's data", module="platform", owner_only=True
)
WORKSPACE_IMPORT = perms.register(
    "workspace.import", "Restore an export into a new workspace", module="platform", owner_only=True
)
