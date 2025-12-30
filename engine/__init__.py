# StoryFx/engine/__init__.py
# -*- coding: utf-8 -*-

from .core import (
    log,
    ensure_adb_connected,
    make_driver,
    open_album,
    long_press_first_thumb,
    tap_share_button,
    unlock_screen_if_needed,
    reset_gallery_home,
    start_gallery,
)

from .engine_intro import run as run_intro
from .engine_multi import run as run_multi

from .platforms import (
    pre_platform_setup,
    share_to_platform,
)
