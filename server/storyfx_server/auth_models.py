"""Closed auth payloads, deliberately excluded from validation error output."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Email(Closed):
    email: str = Field(min_length=3, max_length=254)

    @field_validator('email')
    @classmethod
    def normalize(cls, value):
        clean = value.strip().casefold()
        if '@' not in clean or any(char.isspace() for char in clean):
            raise ValueError('INVALID_EMAIL')
        return clean


class PasswordLogin(Email):
    password: str = Field(min_length=1, max_length=512)


class OtpVerify(Email):
    code: str = Field(min_length=6, max_length=10, pattern=r'^\d+$')


class PasswordUpdate(Closed):
    password: str = Field(min_length=12, max_length=512)
    confirmation: str = Field(min_length=12, max_length=512)


class AgentStart(Closed):
    installation_id: UUID
    name: str = Field(min_length=1, max_length=80)
    android_version: str = Field(min_length=1, max_length=40)
    app_version: str = Field(min_length=1, max_length=40)
    state: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')
    device_nonce: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')
    code_challenge: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')
    code_challenge_method: Literal['S256']
    redirect_uri: Literal['storyfx-android://auth/callback']


class AgentAuthorize(Closed):
    request_id: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')


class AgentExchange(Closed):
    ticket: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')
    state: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')
    device_nonce: str = Field(min_length=43, max_length=43, pattern=r'^[A-Za-z0-9_-]+$')
    installation_id: UUID
    code_verifier: str = Field(min_length=43, max_length=128, pattern=r'^[A-Za-z0-9._~-]+$')
