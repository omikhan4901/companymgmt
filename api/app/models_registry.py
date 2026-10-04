"""Imports every model so metadata is complete (for Alembic and the isolation tests)."""

from app.core import audit, events, outbox, ratelimit  # noqa: F401
from app.core.models import Base
from app.modules.announcements import models as announcements_models  # noqa: F401
from app.modules.attendance import models as attendance_models  # noqa: F401
from app.modules.automations import models as automations_models  # noqa: F401
from app.modules.customers import models as customers_models  # noqa: F401
from app.modules.documents import models as documents_models  # noqa: F401
from app.modules.expenses import models as expenses_models  # noqa: F401
from app.modules.leave import models as leave_models  # noqa: F401
from app.modules.notifications import models as notifications_models  # noqa: F401
from app.modules.payroll import models as payroll_models  # noqa: F401
from app.modules.people import models as people_models  # noqa: F401
from app.modules.platform import ai_models  # noqa: F401
from app.modules.platform import models as platform_models  # noqa: F401
from app.modules.reports import models as reports_models  # noqa: F401
from app.modules.sales import models as sales_models  # noqa: F401
from app.modules.tasks import models as tasks_models  # noqa: F401

metadata = Base.metadata
