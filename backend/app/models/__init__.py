"""SQLAlchemy ORM models (PRD section 27). Import this package before calling
`init_db()` so every table is registered on `Base.metadata`.
"""
from backend.app.models.experiment import Experiment  # noqa: F401
from backend.app.models.failure import Failure  # noqa: F401
from backend.app.models.metric import Metric  # noqa: F401
from backend.app.models.sample_event import SampleEvent  # noqa: F401
from backend.app.models.worker import Worker  # noqa: F401
