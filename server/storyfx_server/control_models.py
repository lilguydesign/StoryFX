"""Transport-free business settings accepted by the private control center."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Named(Strict):
    name: str = Field(min_length=1, max_length=80, pattern=r'^[^\x00-\x1f]+$')


class Profile(Named):
    enabled: bool = True
    offset_minutes: int = Field(default=0, ge=-10080, le=10080)
    label: str = Field(default='', max_length=80)


class Album(Named):
    kind: str = Field(default='multi', max_length=40)
    album_size: int = Field(default=0, ge=0, le=100000)
    count_per_post: int = Field(default=1, ge=1, le=1000)


class System(Named):
    times: list[str] = Field(default_factory=list, max_length=96)

    @field_validator('times')
    @classmethod
    def clocks(cls, values):
        from .legacy_preview import _clock
        for value in values:
            _clock(value)
        if len(set(values)) != len(values):
            raise ValueError('DUPLICATE_TIME')
        return sorted(values)


class Page(Named):
    country: str = Field(min_length=1, max_length=80)


class Matrix(Named):
    device: str = Field(min_length=1, max_length=80)
    platform: Literal['WhatsApp', 'Facebook', 'Instagram', 'TikTok']
    system: str = Field(min_length=1, max_length=80)
    engine: Literal['intro', 'multi', 'intro+multi']
    album: str = Field(default='', max_length=80)
    album2: str = Field(default='', max_length=80)
    count: int = Field(default=1, ge=1, le=1000)
    page: str = Field(default='', max_length=80)
    page_name: str = Field(default='', max_length=80)


class Locator(Named):
    platform: Literal['WhatsApp', 'Facebook', 'Instagram', 'TikTok']
    xpath: str = Field(min_length=1, max_length=1024)


MODELS = dict(profiles=Profile, albums=Album, systems=System, pages=Page,
              matrix=Matrix, locators=Locator)


class Change(Strict):
    revision: int = Field(ge=0)
    value: dict


class Removal(Strict):
    revision: int = Field(ge=0)


class Launch(Strict):
    occurrence_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    revision: int = Field(ge=0)
