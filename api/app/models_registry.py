"""Imports every model so metadata is complete (for Alembic and the isolation tests)."""

from app.core import audit, outbox, ratelimit  # noqa: F401
from app.core.models import Base
from app.modules.attendance import models as attendance_models  # noqa: F401
from app.modules.people import models as people_models  # noqa: F401
from app.modules.platform import models as platform_models  # noqa: F401

metadata = Base.metadata
