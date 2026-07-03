import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import HealthCheck, MonitoredUrl

PING_TIMEOUT_SECONDS = 10.0


def create_url(db: Session, url: str) -> MonitoredUrl:
    monitored = MonitoredUrl(url=url)
    db.add(monitored)
    db.commit()
    db.refresh(monitored)
    return monitored


def delete_url(db: Session, url_id: int) -> bool:
    monitored = db.get(MonitoredUrl, url_id)
    if monitored is None:
        return False
    db.delete(monitored)
    db.commit()
    return True


def list_urls(db: Session) -> list[MonitoredUrl]:
    return db.scalars(select(MonitoredUrl).order_by(MonitoredUrl.id)).all()


def get_url_history(db: Session, url_id: int, limit: int = 20) -> list[HealthCheck]:
    return db.scalars(
        select(HealthCheck)
        .where(HealthCheck.url_id == url_id)
        .order_by(desc(HealthCheck.checked_at))
        .limit(limit)
    ).all()


def get_latest_check(db: Session, url_id: int) -> HealthCheck | None:
    return db.scalars(
        select(HealthCheck)
        .where(HealthCheck.url_id == url_id)
        .order_by(desc(HealthCheck.checked_at))
        .limit(1)
    ).first()


def get_latest_checks(db: Session) -> dict[int, HealthCheck]:
    """Latest check per URL in one query (Postgres DISTINCT ON)."""
    rows = db.scalars(
        select(HealthCheck)
        .distinct(HealthCheck.url_id)
        .order_by(HealthCheck.url_id, desc(HealthCheck.checked_at))
    ).all()
    return {check.url_id: check for check in rows}


def ping_url(url: str) -> HealthCheck:
    start = time.perf_counter()
    checked_at = datetime.now(timezone.utc)

    try:
        with httpx.Client(
            timeout=PING_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": "uptime-monitor/1.0"},
        ) as client:
            response = client.get(url)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        is_up = response.status_code < 500

        return HealthCheck(
            status_code=response.status_code,
            response_time_ms=elapsed_ms,
            is_up=is_up,
            error_message=None if is_up else f"HTTP {response.status_code}",
            checked_at=checked_at,
        )
    except httpx.RequestError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return HealthCheck(
            status_code=None,
            response_time_ms=elapsed_ms,
            is_up=False,
            error_message=str(exc)[:512],
            checked_at=checked_at,
        )


def record_check(db: Session, url_id: int, check: HealthCheck) -> HealthCheck:
    check.url_id = url_id
    db.add(check)
    db.commit()
    db.refresh(check)
    return check
