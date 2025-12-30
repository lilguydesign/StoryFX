# ui/tabs/__init__.py
# -*- coding: utf-8 -*-

from .ui_tabs_launcher import build_launcher_tab, update_platform_fields
from .ui_tabs_admin import (
    build_profiles_tab,
    build_systems_tab,
    build_matrix_tab,
    build_albums_tab,
    build_pages_tab,  # 👈
    refresh_profiles_table,
    refresh_systems_table,
    refresh_matrix_table,
    refresh_albums_table,
)
from .ui_tabs_locators import build_locators_tab
from .ui_tabs_sched_devices import make_sched_tab, build_devices_tab
