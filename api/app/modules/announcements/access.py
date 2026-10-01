"""Announcement permissions.

Everyone reads what's addressed to them. `announcements.post` writes to everyone, or (for
scoped roles) only to departments inside the poster's own scope.
"""

from app.core import permissions as perms

READ = perms.register("announcements.read", "Read announcements", module="announcements")
POST = perms.register(
    "announcements.post",
    "Post announcements and see who has read them",
    module="announcements",
    scoped=True,
)
