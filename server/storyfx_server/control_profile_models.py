"""Private transport metadata; editing never executes ADB or changes permissions."""
import ipaddress
from pydantic import BaseModel, ConfigDict, Field, field_validator

IDENTITY = r'^[A-Za-z0-9_.:\[\]+-]*$'
PACKAGE = r'^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+$'
ACTIVITY = r'^[A-Za-z0-9_.]+$'


class Gallery(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    appPackage: str = Field(default='', max_length=160)
    appActivity: str = Field(default='', max_length=200)

    @field_validator('appPackage', 'appActivity')
    @classmethod
    def component(cls, value, info):
        import re
        if value and not re.fullmatch(PACKAGE if info.field_name == 'appPackage' else ACTIVITY, value):
            raise ValueError('INVALID_ANDROID_COMPONENT')
        return value


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80, pattern=r'^[^\x00-\x1f]+$')
    enabled: bool = True
    offset_minutes: int = Field(default=0, ge=-10080, le=10080)
    label: str = Field(default='', max_length=80)
    device_id: str = Field(default='', max_length=160, pattern=IDENTITY)
    adb_serial: str = Field(default='', max_length=160, pattern=IDENTITY)
    tcpip_ip: str = Field(default='', max_length=45)
    tcpip_port: int = Field(default=5555, ge=1, le=65535)
    platform_version: str = Field(default='', max_length=16, pattern=r'^[0-9.]*$')
    appium_overrides: dict = Field(default_factory=dict)
    gallery: Gallery = Field(default_factory=Gallery)

    @field_validator('tcpip_ip')
    @classmethod
    def address(cls, value):
        if value:
            ipaddress.ip_address(value)
        return value

    @field_validator('appium_overrides')
    @classmethod
    def capabilities(cls, value):
        numeric = {'uiautomator2ServerLaunchTimeout', 'uiautomator2ServerInstallTimeout',
                   'adbExecTimeout', 'newCommandTimeout', 'waitForIdleTimeout',
                   'waitForSelectorTimeout', 'systemPort', 'mjpegServerPort'}
        booleans = {'disableWindowAnimation', 'skipDeviceInitialization',
                    'ignoreHiddenApiPolicyError', 'unicodeKeyboard', 'resetKeyboard'}
        for raw, item in value.items():
            name = raw.removeprefix('appium:')
            if name in numeric:
                if type(item) is not int or not 0 <= item <= 600000:
                    raise ValueError('INVALID_CAPABILITY_VALUE')
                if name == 'systemPort' and not 8200 <= item <= 8299:
                    raise ValueError('INVALID_SYSTEM_PORT')
                if name == 'mjpegServerPort' and not 1 <= item <= 65535:
                    raise ValueError('INVALID_MJPEG_PORT')
            elif name in booleans:
                if type(item) is not bool:
                    raise ValueError('INVALID_CAPABILITY_VALUE')
            elif name in {'noReset', 'fullReset', 'autoGrantPermissions'}:
                if type(item) is not bool or item != (name == 'noReset'):
                    raise ValueError('DATA_OR_PERMISSION_CHANGE_REFUSED')
            else:
                raise ValueError('CAPABILITY_NOT_ALLOWED')
        if len(value) > 20:
            raise ValueError('TOO_MANY_CAPABILITIES')
        return value
