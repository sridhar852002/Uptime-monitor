import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.database import Base, engine, get_db, wait_for_db
from app.models import MonitoredUrl
from app.schemas import HealthCheckOut, MessageOut, MonitoredUrlOut, UrlCreate
from app.scheduler import monitor_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def serialize_url(db: Session, monitored: MonitoredUrl) -> MonitoredUrlOut:
    latest = crud.get_latest_check(db, monitored.id)
    return MonitoredUrlOut(
        id=monitored.id,
        url=monitored.url,
        created_at=monitored.created_at,
        latest_check=latest,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    Base.metadata.create_all(bind=engine)

    # monitor_loop runs its first check immediately, so no explicit
    # startup check is needed here.
    stop_event = asyncio.Event()
    task = asyncio.create_task(monitor_loop(stop_event))

    yield

    stop_event.set()
    await task


app = FastAPI(title="Uptime Monitor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=MessageOut)
def health():
    return MessageOut(message="ok")


@app.get("/urls", response_model=list[MonitoredUrlOut])
def get_urls(db: Session = Depends(get_db)):
    monitored_urls = crud.list_urls(db)
    latest_by_url = crud.get_latest_checks(db)
    return [
        MonitoredUrlOut(
            id=monitored.id,
            url=monitored.url,
            created_at=monitored.created_at,
            latest_check=latest_by_url.get(monitored.id),
        )
        for monitored in monitored_urls
    ]


@app.post("/urls", response_model=MonitoredUrlOut, status_code=status.HTTP_201_CREATED)
def add_url(payload: UrlCreate, db: Session = Depends(get_db)):
    url = str(payload.url)
    existing = db.scalars(select(MonitoredUrl).where(MonitoredUrl.url == url)).first()
    if existing:
        raise HTTPException(status_code=409, detail="URL is already being monitored")

    try:
        monitored = crud.create_url(db, url)
    except IntegrityError:
        # Concurrent POSTs can pass the check above; the unique constraint wins.
        db.rollback()
        raise HTTPException(status_code=409, detail="URL is already being monitored")
    check = crud.ping_url(url)
    crud.record_check(db, monitored.id, check)
    return serialize_url(db, monitored)


@app.delete("/urls/{url_id}", response_model=MessageOut)
def remove_url(url_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_url(db, url_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="URL not found")
    return MessageOut(message="deleted")


@app.get("/urls/{url_id}/history", response_model=list[HealthCheckOut])
def get_history(url_id: int, db: Session = Depends(get_db)):
    monitored = db.get(MonitoredUrl, url_id)
    if monitored is None:
        raise HTTPException(status_code=404, detail="URL not found")
    return crud.get_url_history(db, url_id)
