# ui/ui_admin/locators_admin.py
# -*- coding: utf-8 -*-

import PySimpleGUI as sg
from ui.ui_paths_helpers import load_locators_dict, save_locators_dict


def handle_locators_events(ev, vals, win):
    """
    Gère 100% de la logique LOCATORS qui était dans app.py :

        -LOC_LOAD-
        -LOC_SAVE-

    ⚠ Ne crée aucun widget.
    ⚠ Ne fait que de la logique sur locators.json.
    """

    # ======================================================================
    # 🔥 1) Chargement d'un locator existant (-LOC_LOAD-)
    # ======================================================================
    if ev == "-LOC_LOAD-":
        platform = vals.get("-LOC_PLATFORM-") or ""
        profile  = vals.get("-LOC_PROFILE-") or "default"
        key      = vals.get("-LOC_KEY-") or ""

        if not platform or not key:
            sg.popup_error("Choisis au moins une plateforme et une clé.")
            return True

        locs = load_locators_dict()
        plat_cfg = locs.get(platform, {})
        key_cfg  = plat_cfg.get(key, {})

        # On essaie d'abord le profile, puis 'default', puis vide
        xpath = key_cfg.get(profile) or key_cfg.get("default") or ""
        win["-LOC_XPATH-"].update(xpath)

        return True

    # ======================================================================
    # 🔥 2) Enregistrement d'un locator (-LOC_SAVE-)
    # ======================================================================
    if ev == "-LOC_SAVE-":
        platform = vals.get("-LOC_PLATFORM-") or ""
        profile  = vals.get("-LOC_PROFILE-") or "default"
        key      = vals.get("-LOC_KEY-") or ""
        xpath    = (vals.get("-LOC_XPATH-") or "").strip()

        if not platform or not key:
            sg.popup_error("Plateforme et clé sont obligatoires.")
            return True

        if not xpath:
            sg.popup_error("XPath vide, rien à enregistrer.")
            return True

        locs = load_locators_dict()

        plat_cfg = locs.setdefault(platform, {})
        key_cfg  = plat_cfg.setdefault(key, {})
        key_cfg[profile] = xpath

        save_locators_dict(locs)
        sg.popup("Locator enregistré.")
        return True

    # ======================================================================
    # Pas un event Locators
    # ======================================================================
    return False
