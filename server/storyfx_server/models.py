"""Closed request contracts: no shell, selectors, publication or filesystem commands."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Enrollment(StrictModel):
    code: str = Field(min_length=16, max_length=16, pattern=r'^[a-fA-F0-9]{16}$')
    installation_id: UUID
    name: str = Field(min_length=1, max_length=80)
    android_version: str = Field(min_length=1, max_length=40)


class Heartbeat(StrictModel):
    battery_percent: int | None = Field(default=None, ge=0, le=100)
    screen_locked: bool
    app_version: str = Field(min_length=1, max_length=40)
    executor: Literal['diagnostic']


class Diagnostic(StrictModel):
    device_id: UUID
    scheduled_at: datetime
    expires_at: datetime

    @field_validator('scheduled_at', 'expires_at')
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('TIMEZONE_REQUIRED')
        return value


class AgentEvent(StrictModel):
    event_id: UUID
    lease_token: str = Field(min_length=32, max_length=128)
    stage: Literal['STARTED', 'DIAGNOSTIC_CONFIRMED']
    detail: Literal['diagnostic_only']


class Renewal(StrictModel):
    lease_token: str = Field(min_length=32, max_length=128)


class Empty(StrictModel):
    pass
