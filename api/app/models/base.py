"""Declarative base and shared column mixins for all ORM models.

Identifier convention (AGENTS.md): every non-reference table has an int
``id`` primary key (``IntIdModel``). Tables whose rows are publicly
identified (referenced in URLs, JWTs, or the public API) additionally carry
a ``uuid`` column (``IntIdUuidModel``); the API exposes that uuid as the
public ``"id"``. Reference tables (text key) use plain ``Base``.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class IntIdModel(Base):
    """Abstract base for tables with an int ``id`` primary key."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)


class IntIdUuidModel(IntIdModel):
    """Abstract base for int-PK tables that also expose a public ``uuid``.

    The uuid is supplied by the API (UUIDv4) before insert. Columns
    created with a ``gen_random_uuid()`` fallback default (e.g.
    ``strength_exercise_sets.uuid``) additionally guarantee a row can
    never exist without a public identifier.
    """

    __abstract__ = True

    uuid: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)


class TimestampMixin:
    """Standard audit columns present on every table.

    ``created_at``/``updated_at`` defaults come from the database;
    ``updated_at`` is kept current by the ``set_updated_at`` trigger defined
    in the migrations. ``deleted_at`` implements soft deletion.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
