"""Document permissions.

Everyone reads the documents meant for them. `documents.manage` publishes, edits and
archives documents, sees all of them and who has acknowledged each.
"""

from app.core import permissions as perms

READ = perms.register("documents.read", "Read documents and acknowledge policies", module="documents")
MANAGE = perms.register(
    "documents.manage", "Publish and edit documents, and see who has acknowledged them", module="documents"
)
