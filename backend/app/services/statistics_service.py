"""Statistics service for death records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from app.database.database import Database
from app.database.models import Death


@dataclass
class StatisticsSummary:
    total_deaths: int
    total_lifespan_seconds: int
    average_lifespan_seconds: float
    by_cause: dict[str, int]
    by_extension: dict[str, int]
    oldest_death: datetime | None
    newest_death: datetime | None


class StatisticsService:
    """Aggregates over death records."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def summary(self) -> StatisticsSummary:
        with self.database.session() as session:
            total = int(session.scalar(select(func.count()).select_from(Death)) or 0)

            if total == 0:
                return StatisticsSummary(
                    total_deaths=0,
                    total_lifespan_seconds=0,
                    average_lifespan_seconds=0.0,
                    by_cause={},
                    by_extension={},
                    oldest_death=None,
                    newest_death=None,
                )

            total_lifespan = int(
                session.scalar(select(func.sum(Death.lifespan_seconds))) or 0
            )
            avg_lifespan = total_lifespan / total

            by_cause = dict(
                session.execute(
                    select(Death.cause, func.count(Death.id)).group_by(Death.cause)
                ).all()
            )
            by_ext = dict(
                session.execute(
                    select(Death.extension, func.count(Death.id)).group_by(
                        Death.extension
                    )
                ).all()
            )
            oldest = session.scalar(select(func.min(Death.deleted_at)))
            newest = session.scalar(select(func.max(Death.deleted_at)))

        return StatisticsSummary(
            total_deaths=total,
            total_lifespan_seconds=total_lifespan,
            average_lifespan_seconds=avg_lifespan,
            by_cause=by_cause,
            by_extension=by_ext,
            oldest_death=oldest,
            newest_death=newest,
        )