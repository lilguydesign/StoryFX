"""Explicit bounded owner scope for catch-up and continuing automation."""
from typing import Literal
from pydantic import Field, field_validator
from .control_models import Strict


class Window(Strict):
    revision: int = Field(ge=0)
    profiles: list[str] = Field(min_length=1, max_length=20)
    platforms: list[Literal['WhatsApp','Facebook','Instagram','TikTok']] = Field(min_length=1,max_length=4)
    start_time: str = Field(default='05:00',pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    end_time: str | None = Field(default=None,pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')

    @field_validator('profiles','platforms')
    @classmethod
    def unique(cls, values):
        if len(values) != len(set(values)) or any(not value or len(value) > 80 for value in values):
            raise ValueError('INVALID_SCOPE')
        return values


class Schedule(Window):
    mode: Literal['auto','manual'] = 'auto'


class Stop(Strict):
    stop_scheduler: bool = True
