"""Database engine/session setup (PRD section 27). Defaults to a local SQLite file so the
backend and its tests run without a live Postgres instance; set DATABASE_URL to point at
Postgres in Docker/production (e.g. postgresql://pulsex:pulsex@postgres:5432/pulsex).
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./pulsex.db")


def create_db_engine(database_url: str | None = None):
    url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def create_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(engine) -> None:
    """Creates all tables. Requires backend.app.models to be imported first so every
    model class has registered itself on Base.metadata."""
    import backend.app.models  # noqa: F401  (side effect: registers tables on Base.metadata)

    Base.metadata.create_all(engine)


_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_local() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = create_session_factory(get_engine())
    return _SessionLocal


def reset_engine_cache() -> None:
    """Test helper: forces get_engine()/get_session_local() to rebuild against the
    current DATABASE_URL (each test uses its own temp SQLite file)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def get_db():
    """FastAPI dependency yielding a request-scoped session."""
    session: Session = get_session_local()()
    try:
        yield session
    finally:
        session.close()
