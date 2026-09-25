"""SQLAlchemy engine, session factory and declarative base.

Using SQLAlchemy keeps all persistence behind one abstraction so the SQLite
default can be swapped for Postgres by changing ``DATABASE_URL`` only.
"""
from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


def _make_engine():
    url = settings.database_url
    connect_args: dict = {}
    if url.startswith("sqlite"):
        # SQLite needs this flag for use across threads (FastAPI workers).
        connect_args = {"check_same_thread": False}
        # Ensure the parent directory for a file-based SQLite DB exists.
        if url.startswith("sqlite:///"):
            db_path = url.replace("sqlite:///", "", 1)
            parent = os.path.dirname(db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Import models so they register on the metadata."""
    from app import models  # noqa: F401  (registers ORM models)

    Base.metadata.create_all(bind=engine)
