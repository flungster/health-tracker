"""Liveness endpoint for the API and its database."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.db.session import get_unit_of_work
from app.db.unit_of_work import UnitOfWork
from app.version import api_version

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health(unit_of_work: UnitOfWork = Depends(get_unit_of_work)) -> dict[str, Any]:
    """Report API and database availability.

    Returns 200 in all cases; the ``status`` field distinguishes a healthy
    stack from a degraded one (database unreachable). The ``version`` field
    reports the deployed API release.
    """
    database_ok = True
    try:
        unit_of_work.session.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    return {
        "status": "ok" if database_ok else "degraded",
        "api": "ok",
        "database": "ok" if database_ok else "unreachable",
        "version": api_version(),
    }
