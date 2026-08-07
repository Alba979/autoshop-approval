from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    """Current UTC time, stored as a naive datetime.

    We deliberately strip tzinfo before returning: SQLite (this project's
    default database) does not round-trip timezone-aware datetimes cleanly
    through SQLAlchemy, so - as is standard practice for SQLite-backed apps -
    every datetime in this codebase is naive and implicitly UTC. If you
    migrate to Postgres, tz-aware columns become an easy, safe upgrade;
    until then, never mix naive and aware datetimes when comparing.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime(), default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
