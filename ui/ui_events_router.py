# ui/ui_events_router.py
# -*- coding: utf-8 -*-
"""
Routeur d’événements COMPLET pour StoryFX.

Analyse THEORIQUEMENT l’ensemble des événements présents dans app.py
et renvoie :
    - "time"
    - "scheduler"
    - "runner"
    - "adb"
    - "admin"
    - "launcher"
    - "matrix"
    - "albums"
    - "systems"
    - "profiles"
    - "locators"
    - "unknown"

Ce routeur est conçu pour couvrir 100 % des événements de app.py.
Il permet à app.py d’être propre, minimal, et déléguer chaque action
au bon module sans jamais rien oublier.
"""


def route_event(ev, vals):

    # ==========================================================
    # 🔥 RUNNER
    # ==========================================================
    if ev in ("-RUN-", "-RUN_STOP-", "-RUNNER-LOG-", "-RUNNER-DONE-"):
        return "runner"

    # ==========================================================
    # 🔥 SCHEDULER
    # ==========================================================
    if ev.startswith("-SCHED-"):
        return "scheduler"

    # ==========================================================
    # 🔥 TEMPS (heure automatique / manuelle)
    # ==========================================================
    if ev.startswith("-TIME_"):
        return "time"

    # ==========================================================
    # 🔥 DEVICES / ADB
    # ==========================================================
    if ev.startswith("-DEV_"):
        return "adb"

    # Navigation rapide
    if ev == "-GOTO_ADMIN-":
        return "launcher"

    # ==========================================================
    # 🔥 ADMIN (Profiles / Systems / Matrix / Albums / Locators)
    # ==========================================================

    # Profiles
    if ev == "-PROF_TABLE-" or ev.startswith("-P_"):
        return "profiles"

    # Systems
    if ev == "-SYS_TABLE-" or ev.startswith("-S_"):
        return "systems"

    # Matrix
    if ev == "-MAT_TABLE-" or ev.startswith("-M_"):
        return "matrix"

    # Albums
    if ev == "-ALB_TABLE-" or ev.startswith("-ALB_"):
        return "albums"

    # Pages   👈 NOUVEAU
    if ev == "-PG_TABLE-" or ev.startswith("-PG_"):
        return "pages"

    # Locators
    if ev.startswith("-LOC_"):
        return "locators"

    # ==========================================================
    # 🔥 Launcher (engine, album, plateforme…)
    # ==========================================================
    if ev in (
        "-ENGINE-", "-ALBUM-", "-ALBUM2-",
        "-PAGE-", "-PAGE_NAME-", "-PLATFORM-",
        "-IGVAR-", "-COUNT-",
        "-CLEAR_LOG-",
    ):
        return "launcher"

    # ==========================================================
    # 🔥 INCONNU
    # ==========================================================
    return "unknown"