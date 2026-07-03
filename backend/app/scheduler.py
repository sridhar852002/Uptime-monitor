import asyncio
import logging
import os

from app import crud
from app.database import SessionLocal

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))


async def check_all_urls() -> int:
    """Ping every registered URL and store the results.

    Pings are synchronous httpx calls, so they run in worker threads
    (concurrently, bounded by the default thread pool) to avoid blocking
    the event loop that also serves API requests.
    """
    db = SessionLocal()
    try:
        urls = await asyncio.to_thread(crud.list_urls, db)
        results = await asyncio.gather(
            *(asyncio.to_thread(crud.ping_url, monitored.url) for monitored in urls)
        )
        for monitored, result in zip(urls, results):
            await asyncio.to_thread(crud.record_check, db, monitored.id, result)
        return len(urls)
    finally:
        db.close()


async def monitor_loop(stop_event: asyncio.Event) -> None:
    logger.info("Monitor loop started (interval=%ss)", CHECK_INTERVAL_SECONDS)

    while not stop_event.is_set():
        try:
            checked = await check_all_urls()
            logger.info("Completed health checks for %s URL(s)", checked)
        except Exception:
            logger.exception("Monitor loop failed while checking URLs")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue

    logger.info("Monitor loop stopped")
