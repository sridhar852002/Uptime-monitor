import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://uptime:uptime@localhost:5432/uptime",
)


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def wait_for_db(max_attempts: int = 30, delay_seconds: float = 1.0) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
            return
        except Exception:
            if attempt == max_attempts:
                raise
            time.sleep(delay_seconds)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
