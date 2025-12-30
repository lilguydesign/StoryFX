# -*- coding: utf-8 -*-
import PySimpleGUI as sg

from ui.ui_devices import ensure_appium_running
from ui.ui_events_router import route_event
from ui.ui_admin.ui_admin import handle_admin_events
from ui.ui_time import (
    init_time_controls,
    auto_refresh_manual_time,
    get_manual_hhmm,
    update_time_selectors_from_profile,
    write_clock_state,          # 👈 AJOUT
)

from ui.ui_scheduler import handle_scheduler_events, stop_scheduler
from ui.ui_runner import handle_runner_events
from ui.ui_devices import auto_connect_all_devices, get_last_usb_serials
from ui.ui_paths_helpers import (
    load_profiles_dict,
    load_systems_dict,
    load_matrix_rows,
    load_albums_dict,
    load_ui_state,
    save_ui_state,
    append_log,
    build_catalog_from_matrix,  # 👈 AJOUT
    INTRO_ALBUM_CHOICES,  # 👈 AJOUT
    MULTI_ALBUM_CHOICES,  # 👈 AJOUT
    CONFIG,
    load_json,
)
from ui.tabs.ui_tabs_launcher import build_launcher_tab, update_platform_fields
from ui.tabs.ui_tabs_admin import (
    build_profiles_tab,
    build_systems_tab,
    build_matrix_tab,
    build_albums_tab,
    build_pages_tab,
    refresh_profiles_table,
    refresh_systems_table,
    refresh_matrix_table,
    refresh_albums_table,
)
from ui.tabs.ui_tabs_sched_devices import build_devices_tab, make_sched_tab
from ui.tabs.ui_tabs_locators import build_locators_tab


def main():
    # print("[StoryFX] Initialisation environnement…")
    # ensure_appium_running()     # ← configure ADB + Appium automatiquement

    sg.theme("DarkBlue3")

    # -------------------------------------------
    # 🔥 1) Construction DES TABS
    # -------------------------------------------
    tab_launcher  = sg.Tab("Launcher",       build_launcher_tab())
    tab_pages     = sg.Tab("Pages",          build_pages_tab())
    tab_profiles  = sg.Tab("Profiles",       build_profiles_tab())
    tab_devices   = sg.Tab("Devices",        build_devices_tab())
    tab_systems   = sg.Tab("Systems",        build_systems_tab())
    tab_matrix    = sg.Tab("Matrix",         build_matrix_tab())
    tab_albums    = sg.Tab("Albums",         build_albums_tab())
    tab_sched     = sg.Tab("Programmation",  make_sched_tab())
    tab_locators  = sg.Tab("Locators",       build_locators_tab())

    layout = [[
        sg.TabGroup(
            [[tab_launcher, tab_pages, tab_profiles, tab_devices, tab_systems, tab_matrix, tab_albums, tab_sched, tab_locators]],
            expand_x=True,
            expand_y=True,
            key="-TABS-"
        )
    ]]

    win = sg.Window("StoryFX – Final Edition", layout, finalize=True, resizable=True)

    # -------------------------------------------
    # 🔥 2) Charger les données
    # -------------------------------------------
    profiles    = load_profiles_dict()
    systems     = load_systems_dict()
    matrix_rows = load_matrix_rows()
    albums_dict = load_albums_dict()
    ui_state    = load_ui_state()

    # Catalogue albums / pages (pages non utilisées ici)
    albums_from_matrix, _, _ = build_catalog_from_matrix(matrix_rows)

    # Combos ALBUMS (les listes viennent déjà de INTRO_ALBUM_CHOICES / MULTI_ALBUM_CHOICES)
    win["-ALBUM-"].update(values=INTRO_ALBUM_CHOICES)
    win["-ALBUM2-"].update(values=MULTI_ALBUM_CHOICES)

    # ⚠️ On NE met plus à jour -PAGE- / -PAGE_NAME- ici,
    # ils sont remplis directement depuis config/pages.json dans build_launcher_tab().

    # -------------------------------------------
    # 🔥 2A) Remplir le Combo PROFIL
    # -------------------------------------------
    profile_names = list(profiles.keys())
    win["-PROFILE-"].update(values=profile_names)

    # Sélectionner automatiquement le premier profil si tu veux
    if profile_names:
        win["-PROFILE-"].update(value=profile_names[0])
        # Appliquer directement les heures & minutes du premier profil
        update_time_selectors_from_profile(
            win,
            profile_names[0],
            systems,
            matrix_rows,
            profiles,
        )

    # -------------------------------------------
    # 🔥 3) Remplir les tables Admin
    # -------------------------------------------
    refresh_profiles_table(win, profiles, matrix_rows)
    refresh_systems_table(win, systems)
    refresh_matrix_table(win, matrix_rows)
    refresh_albums_table(win, albums_dict)

    # -------------------------------------------
    # 🔥 4) Initialiser HEURE (AUTO)
    # -------------------------------------------
    clock_path = CONFIG / "scheduler_clock.json"

    init_time_controls(win, clock_path)

    # -------------------------------------------
    # 🔥 5) Contextes (références runner + scheduler)
    # -------------------------------------------
    scheduler_ref = {"proc": None}
    runner_ref    = {"proc": None}

    editing_manual_time = False
    tick_counter = 0

    # -------------------------------------------
    # 🔥 6) BOUCLE PRINCIPALE
    # -------------------------------------------
    while True:
        ev, vals = win.read(timeout=100)

        if ev in (sg.WINDOW_CLOSED, "Quitter"):
            break

        # 1) ROUTAGE DE L'ÉVÉNEMENT
        category = route_event(ev, vals)

        # 🔥 Quand on change de PROFIL dans le launcher :
        # → on met à jour les heures (systems.json) et les minutes (offset_minutes)
        if ev == "-PROFILE-":
            profile_name = vals.get("-PROFILE-")
            if profile_name:
                update_time_selectors_from_profile(
                    win,
                    profile_name,
                    systems,
                    matrix_rows,
                    profiles,
                )
            continue
        # --------------------------------------
        # A) UI TEMPS
        # --------------------------------------
        if category == "time":

            # 1) Toggle Auto ↔ Manuel
            if ev in ("-TIME_AUTO-", "-TIME_MANUAL-"):
                auto_mode = vals["-TIME_AUTO-"]

                if auto_mode:
                    # Repasser en mode AUTO (heure PC) et écrire dans le JSON
                    init_time_controls(win, clock_path)
                    append_log(win, "[Time] Mode auto activé.")
                else:
                    # Passage en MANUEL : déverrouiller HH/MM
                    for k in ("-TIME_HH-", "-TIME_MM-"):
                        win[k].update(disabled=False)

                    # On enregistre l'heure manuelle actuelle comme point de départ
                    hhmm = get_manual_hhmm(vals)
                    if hhmm:
                        write_clock_state(clock_path, "manual", hhmm)
                        append_log(win, f"[Time] Mode manuel activé : {hhmm}")

                editing_manual_time = False
                continue

            # 2) L’utilisateur change HH ou MM en mode MANUEL
            if ev in ("-TIME_HH-", "-TIME_MM-") and vals.get("-TIME_MANUAL-"):
                hhmm = get_manual_hhmm(vals)
                if hhmm:
                    write_clock_state(clock_path, "manual", hhmm)
                    append_log(win, f"[Time] Nouvelle heure manuelle : {hhmm}")
                editing_manual_time = False
                continue


        # --------------------------------------
        # B) ADMIN (Profiles / Systems / Matrix / Albums / Pages / Locators)
        # --------------------------------------
        if category in ("profiles", "systems", "matrix", "albums", "pages", "locators"):
            handled = handle_admin_events(
                ev, vals, win,
                profiles, systems, matrix_rows, albums_dict
            )
            if handled:
                continue

        # --------------------------------------
        # C) SCHEDULER
        # --------------------------------------
        if category == "scheduler":
            handled = handle_scheduler_events(
                ev, vals, win,
                scheduler_ref,
                albums_dict,
                matrix_rows
            )
            if handled:
                continue

        # --------------------------------------
        # D) RUNNER
        # --------------------------------------
        if category == "runner":
            handled = handle_runner_events(
                ev, vals, win,
                runner_ref,
                profiles,
                albums_dict,
                "ui_state.json"
            )
            if handled:
                continue

        # --------------------------------------
        # E) DEVICES
        # --------------------------------------
        # --------------------------------------
        # E) DEVICES
        # --------------------------------------
        if category == "adb":

            # --- 1) Scanner & connecter (USB → Wi-Fi)
            if ev == "-DEV_SCAN_CONNECT-":
                log = auto_connect_all_devices(profiles)
                win["-DEV_LOG-"].update(log)
                continue

            # --- 2) `adb devices` PRO
            if ev in ("-DEV_LIST-", "-DEV_DEVICES-"):
                from ui.ui_devices import list_devices_pro
                log = list_devices_pro()
                win["-DEV_LOG-"].update(log)
                continue

            # --- 3) Copier serial(s) détectés en USB
            if ev == "-DEV_COPY_SERIAL-":
                serials = get_last_usb_serials()
                if serials:
                    sg.clipboard_set(", ".join(serials))
                    append_log(win, f"[Devices] Serials copiés : {serials}")
                else:
                    sg.popup_error("Aucun serial USB détecté.\nClique d'abord sur Scanner & connecter.")
                continue

            # --- 4) Connecter TOUT (connexion PRO)
            if ev == "-DEV_CONNECT_ALL-":
                from ui.ui_devices import connect_all_devices
                log = connect_all_devices()
                win["-DEV_LOG-"].update(log)
                continue

            # --- 5) Déconnecter TOUT (reset adb)
            if ev == "-DEV_DISCONNECT-":
                from ui.ui_devices import disconnect_all_devices
                log = disconnect_all_devices()
                win["-DEV_LOG-"].update(log)
                continue

            # --- 6) Effacer le log
            if ev == "-DEV_CLEAR-":
                win["-DEV_LOG-"].update("")
                continue


        # F) LAUNCHER (albums, plateformes, engine…)
        if category == "launcher":

            # 1) Effacer le log COMPLET
            if ev == "-CLEAR_LOG-":
                win["-LOG-"].update("")
                continue

            # 2) Aller automatiquement vers l’onglet Admin (Profiles)
            if ev == "-GOTO_ADMIN-":
                try:
                    win["-TABS-"].Widget.select(1)   # Onglet Profiles
                except Exception:
                    pass
                continue

            # 3) Changement de plateforme
            if ev == "-PLATFORM-":
                update_platform_fields(win, vals["-PLATFORM-"])
                continue

            # 4) Changement d’album
            #    - L'album intro NE TOUCHE JAMAIS à Count (toujours 1 pour l'intro)
            #    - Seul l'album multi met à jour Count, et seulement si l'engine
            #      n'est pas "intro".
            if ev in ("-ALBUM-", "-ALBUM2-"):

                # Si c'est l'album intro → on ne change rien
                if ev == "-ALBUM-":
                    continue

                # Ici on sait que ev == "-ALBUM2-" (album multi)
                album_name = (vals.get("-ALBUM2-") or "").strip()
                engine = (vals.get("-ENGINE-") or "").strip()

                # Si l'engine est "intro" → Count reste 1
                if engine == "intro":
                    win["-COUNT-"].update(value=1)
                    continue

                # Sinon (multi ou intro+multi), on synchronise Count avec l'album
                if album_name and isinstance(albums_dict, dict):
                    cfg = albums_dict.get(album_name) or {}
                    default_count = cfg.get("count_per_post") or cfg.get("album_size") or 0
                    try:
                        default_count = int(default_count)
                    except Exception:
                        default_count = 0

                    if default_count <= 0:
                        default_count = 1  # sécurité

                    win["-COUNT-"].update(value=default_count)

                continue

        # --------------------------------------
        # G) AUTO-REFRESH DE L'HEURE MANUELLE
        # --------------------------------------
        tick_counter += 1
        if tick_counter >= 10:
            tick_counter = 0
            if vals.get("-TIME_MANUAL-") and not editing_manual_time:
                auto_refresh_manual_time(win, editing_manual_time)

    # Arrêter scheduler si encore en cours
    if scheduler_ref["proc"] and scheduler_ref["proc"].poll() is None:
        stop_scheduler(win, scheduler_ref)

    win.close()

if __name__ == "__main__":
    main()
