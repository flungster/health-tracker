"""Database engine and the request-scoped unit-of-work dependency.

The engine (and its connection pool) is created once per process and shared,
because pooling is only useful when the pool outlives a single request. The
per-request object is a :class:`~app.db.unit_of_work.UnitOfWork` wrapping one
session: it is handed to the service layer, which stages reads and writes and
commits when a business operation succeeds. On error the session is rolled
back, and it is always closed.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.unit_of_work import UnitOfWork

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating it on first use.

    This is the one intentional process-wide singleton: the connection pool
    must be shared across requests to be effective.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def make_session_factory() -> sessionmaker[Session]:
    """Build a session factory bound to the process-wide engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_unit_of_work() -> Iterator[UnitOfWork]:
    """FastAPI dependency yielding one unit of work (one session) per request.

    The session is rolled back on error and always closed. Services receive the
    unit of work and commit through it; they never create or close sessions.
    """
    session = make_session_factory()()
    unit_of_work = UnitOfWork(session)
    try:
        yield unit_of_work
    except Exception:
        unit_of_work.rollback()
        raise
    finally:
        unit_of_work.close()
