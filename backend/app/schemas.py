from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class UrlCreate(BaseModel):
    url: HttpUrl


class LatestCheck(BaseModel):
    status_code: int | None
    response_time_ms: int | None
    is_up: bool
    error_message: str | None
    checked_at: datetime | None

    model_config = {"from_attributes": True}


class MonitoredUrlOut(BaseModel):
    id: int
    url: str
    created_at: datetime
    latest_check: LatestCheck | None = None

    model_config = {"from_attributes": True}


class HealthCheckOut(BaseModel):
    id: int
    status_code: int | None
    response_time_ms: int | None
    is_up: bool
    error_message: str | None
    checked_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    message: str = Field(default="ok")
