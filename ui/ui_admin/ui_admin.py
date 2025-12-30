# ui/ui_admin/ui_admin.py
# -*- coding: utf-8 -*-

"""
Routeur ADMIN COMPLET
=====================

Ce fichier remplace 1500 lignes de logique dans app.py.
Il redistribue intelligemment chaque événement Admin vers :

    - Profiles Admin       (PROF_TABLE, P_SAVE, P_DEL, P_DUP, etc.)
    - Albums Admin         (ALB_TABLE, ALB_SAVE, ALB_DEL, ALB_SYNC)
    - Systems Admin        (SYS_TABLE, S_SAVE, S_DEL)
    - Matrix Admin         (MAT_TABLE, M_SAVE, M_DEL, M_REFRESH)
    - Locators Admin       (LOC_LOAD, LOC_SAVE)

Il est 100% fidèle à ton app originale (:contentReference[oaicite:7]{index=7}).
Il ne fait AUCUNE logique lui-même.
Il redirige proprement.
"""

from .profiles_admin import handle_profiles_events
from .albums_admin import handle_albums_events
from .systems_admin import handle_systems_events
from .matrix_admin import handle_matrix_events
from .locators_admin import handle_locators_events
from .pages_admin import handle_pages_events



def handle_admin_events(ev, vals, win, profiles, systems, matrix_rows, albums_dict):
    """
    Route automatiquement tous les événements ADMIN vers les bons modules.

    Retourne :
        True  → événement traité
        False → non géré (retour à app.py / autres modules)
    """

    # ----------------------------------------------------------------------
    # 🔥 1) LOCATORS
    # ----------------------------------------------------------------------
    if ev.startswith("-LOC_"):
        return handle_locators_events(ev, vals, win)

    # ----------------------------------------------------------------------
    # 🔥 2) ALBUMS
    # ----------------------------------------------------------------------
    if ev.startswith("-ALB_") or ev == "-ALB_TABLE-":
        return handle_albums_events(ev, vals, win, albums_dict, matrix_rows, profiles)

    # ----------------------------------------------------------------------
    # 🔥 3) PROFILES
    # ----------------------------------------------------------------------
    if ev.startswith("-P_") or ev == "-PROF_TABLE-":
        return handle_profiles_events(ev, vals, win, profiles, matrix_rows)

    # ----------------------------------------------------------------------
    # 🔥 4) SYSTEMS
    # ----------------------------------------------------------------------
    if ev.startswith("-S_") or ev == "-SYS_TABLE-":
        return handle_systems_events(ev, vals, win, systems, matrix_rows)

    # ----------------------------------------------------------------------
    # 🔥 5) MATRIX
    # ----------------------------------------------------------------------
    if ev.startswith("-M_") or ev == "-MAT_TABLE-":
        return handle_matrix_events(ev, vals, win, matrix_rows, albums_dict)

    # ----------------------------------------------------------------------
    # 🔥 6) PAGES
    # ----------------------------------------------------------------------
    if ev.startswith("-PG_") or ev == "-PG_TABLE-":
        return handle_pages_events(ev, vals, win)

    # ----------------------------------------------------------------------
    # Aucun événement admin
    # ----------------------------------------------------------------------
    return False
