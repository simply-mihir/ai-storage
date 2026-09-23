"""Postgres system of record — submitted_scenarios table with graceful degradation."""

from __future__ import annotations

import logging
import os
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class SubmittedScenario(Base):
    __tablename__ = "submitted_scenarios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime, server_default=text("NOW()"))
    report_md = Column(Text, nullable=True)


_engine = None
_SessionLocal = None


def _get_database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def _init_engine() -> bool:
    global _engine, _SessionLocal
    url = _get_database_url()
    if not url:
        logger.warning("DATABASE_URL not set — PG recording disabled")
        return False
    try:
        _engine = create_engine(url, pool_pre_ping=True, pool_size=2)
        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(bind=_engine)
        return True
    except Exception:
        logger.warning("Could not connect to Postgres — recording disabled", exc_info=True)
        _engine = None
        _SessionLocal = None
        return False


def save_scenario(
    scenario_id: str,
    payload: dict,
    report_md: str | None = None,
) -> bool:
    """Persist a submitted scenario. Returns False on failure (graceful degradation)."""
    if _SessionLocal is None and not _init_engine():
        return False
    try:
        session = _SessionLocal()
        try:
            row = SubmittedScenario(
                id=scenario_id,
                payload=payload,
                report_md=report_md,
            )
            session.add(row)
            session.commit()
            return True
        except Exception:
            session.rollback()
            logger.warning("Failed to save scenario %s", scenario_id, exc_info=True)
            return False
        finally:
            session.close()
    except Exception:
        logger.warning("Session creation failed for scenario %s", scenario_id, exc_info=True)
        return False


def get_scenario(scenario_id: str) -> dict | None:
    """Retrieve a submitted scenario by ID. Returns None if PG unavailable."""
    if _SessionLocal is None and not _init_engine():
        return None
    try:
        session = _SessionLocal()
        try:
            row = session.query(SubmittedScenario).get(scenario_id)
            if row is None:
                return None
            return {
                "id": row.id,
                "payload": row.payload,
                "created_at": str(row.created_at) if row.created_at else None,
                "report_md": row.report_md,
            }
        finally:
            session.close()
    except Exception:
        logger.warning("Failed to retrieve scenario %s", scenario_id, exc_info=True)
        return None


def reset() -> None:
    """Reset the module-level engine (for testing)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
