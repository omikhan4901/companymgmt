"""Privacy permissions."""

from app.core import permissions as perms

WORKSPACE_EXPORT = perms.register(
    "workspace.export", "Export all of the workspace's data", module="platform", owner_only=True
)
