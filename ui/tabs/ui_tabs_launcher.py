# -*- coding: utf-8 -*-
import PySimpleGUI as sg
import json
from pathlib import Path

from ui.ui_paths_helpers import (
    MATRIX,
    save_json,
    build_catalog_from_matrix,
)


def build_launcher_tab():
    """
    Onglet Launcher 100% format 24h.
    - PLUS DE AM/PM
    - HH & MM seront mis à jour dynamiquement par update_time_selectors_from_profile()
    """

    engines   = ["intro", "multi", "intro+multi"]
    platforms = ["WhatsApp", "Facebook", "Instagram", "TikTok"]

    # 🔥 Charger la liste des pays/pages depuis pages.json
    pages_file = Path(__file__).resolve().parents[2] / "config" / "pages.json"
    countries = []
    page_names = []
    if pages_file.exists():
        with open(pages_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for entry in data.get("pages", []):
                countries.append(entry.get("country", ""))
                page_names.append(entry.get("name", ""))
    countries = sorted(set(countries))
    page_names = sorted(set(page_names))

    layout = [
        # --- PROFIL ---
        [
            sg.Text("Profil"),
            sg.Combo(
                [], key="-PROFILE-", size=(28, 1),
                readonly=True, enable_events=True
            ),
        ],

        # --- ENGINE ---
        [
            sg.Text("Engine"),
            sg.Combo(
                engines, default_value="intro",
                key="-ENGINE-", size=(12, 1),
                readonly=True, enable_events=True
            ),
        ],

        # --- ALBUM INTRO ---
        [
            sg.Text("Album (intro)"),
            sg.Combo(
                [], key="-ALBUM-", size=(28, 1),
                readonly=True, enable_events=True
            ),
            sg.Button("⚙", key="-EDIT_ALBUMS-", size=(3, 1)),
        ],

        # --- ALBUM MULTI ---
        [
            sg.Text("Album (multi)"),
            sg.Combo(
                [], key="-ALBUM2-", size=(28, 1),
                readonly=True, enable_events=True
            ),
        ],

        # --- COUNT ---
        [
            sg.Text("Count"),
            sg.Spin(
                [i for i in range(1, 60)],
                initial_value=11,
                key="-COUNT-", size=(5, 1)
            ),
        ],

        # --- PLATEFORME ---
        [
            sg.Text("Plateforme"),
            sg.Combo(
                platforms, default_value="WhatsApp",
                key="-PLATFORM-", size=(14, 1),
                readonly=True, enable_events=True
            ),
        ],

        # --- PAYS / PAGE FACEBOOK ---
        [
            sg.Text("Pays"),
            sg.Combo(countries, key="-PAGE-", size=(25, 1), readonly=True),  # 🔥 plus large et lit pages.json

            sg.Text("Page"),
            sg.Combo(page_names, key="-PAGE_NAME-", size=(40, 1), readonly=True),

            sg.Button("⚙", key="-EDIT_PAGES-", size=(3, 1)),
        ],

        [sg.HorizontalSeparator()],

        # --- TEMPS DU SCHEDULER — FORMAT 24H ---
        [
            sg.Text("Temps scheduler"),
            sg.Radio("Auto (PC)", "TIME_MODE", key="-TIME_AUTO-", default=True, enable_events=True),
            sg.Radio("Manuel", "TIME_MODE", key="-TIME_MANUAL-", enable_events=True),

            sg.Text("Heure"),

            # 🔥 FORMAT 24H — VALEURS PAR DÉFAUT VIDES, REMPLIES PAR update_time_selectors_from_profile()
            sg.Combo(
                [],
                key="-TIME_HH-",
                size=(4, 40),  # 👈 20 lignes affichées d’un coup
                readonly=True,
                enable_events=True,
                # sbar_width=0,  # 👈 enlève la barre de scroll disgracieuse
            ),

            sg.Text(":"),

            sg.Combo(
                [],
                key="-TIME_MM-",
                size=(4, 40),  # 👈 même height pour cohérence
                readonly=True,
                enable_events=True,
                # sbar_width=0,
            )

        ],

        # --- BOUTONS ---
        [
            sg.Button("▶ Démarrer scheduler", key="-SCHED-START-L-", button_color=("white", "green")),
            sg.Button("■ Arrêter scheduler", key="-SCHED-STOP-L-", button_color=("white", "firebrick4")),
            sg.Button("▶ Lancer", key="-RUN-", bind_return_key=True),
            sg.Button("Stopper", key="-RUN_STOP-"),
            sg.Button("Effacer", key="-CLEAR_LOG-"),
            sg.Button("Admin", key="-GOTO_ADMIN-"),
            sg.Push(),
            sg.Button("Quitter"),
        ],

        # --- LOGS ---
        [
            sg.Multiline(
                key="-LOG-", size=(120, 25),
                autoscroll=True, disabled=True,
                expand_x=True, expand_y=True,
                font=("Consolas", 9)
            )
        ],
    ]

    return layout


def update_platform_fields(win, platform: str):
    """Active/désactive les champs suivant la plateforme choisie."""
    platform = (platform or "").strip()

    fb_active = (platform == "Facebook")
    win["-PAGE-"].update(disabled=not fb_active)
    win["-PAGE_NAME-"].update(disabled=not fb_active)
    win["-EDIT_PAGES-"].update(disabled=not fb_active)

    if not fb_active:
        win["-PAGE-"].update(value="")
        win["-PAGE_NAME-"].update(value="")


def edit_albums(win, matrix_rows):
    albums, _, _, _ = build_catalog_from_matrix(matrix_rows)

    layout = [
        [sg.Text("Sélectionne un album et renomme-le")],
        [sg.Listbox(albums, key="-ALIST-", size=(30, 8), enable_events=True)],
        [sg.Text("Nouveau nom"), sg.Input(key="-ANEW-")],
        [sg.Button("Renommer"), sg.Button("Fermer")],
    ]
    dlg = sg.Window("Albums", layout, modal=True)

    while True:
        ev, vals = dlg.read()
        if ev in (sg.WINDOW_CLOSED, "Fermer"):
            break

        if ev == "-ALIST-":
            if vals["-ALIST-"]:
                dlg["-ANEW-"].update(vals["-ALIST-"][0])
            continue

        if ev == "Renommer":
            if not vals["-ALIST-"]:
                sg.popup_error("Choisis un album dans la liste.")
                continue
            old = vals["-ALIST-"][0]
            new = vals["-ANEW-"].strip()
            if not new:
                sg.popup_error("Saisis un nouveau nom.")
                continue

            # Mettre à jour Matrix
            for r in matrix_rows:
                if r.get("album") == old:
                    r["album"] = new
                if r.get("album2") == old:
                    r["album2"] = new

            albums, _, _, _ = build_catalog_from_matrix(matrix_rows)
            dlg["-ALIST-"].update(albums)
            sg.popup("Album renommé.")

    dlg.close()
    save_json(MATRIX, {"rows": matrix_rows})

    # Recalcul complet (intro vs multi)
    updated_albums, page_codes, page_names = build_catalog_from_matrix(matrix_rows)

    # Mise à jour du Launcher
    win["-ALBUM-"].update(values=updated_albums)
    win["-ALBUM2-"].update(values=updated_albums)

    # Mise à jour Pays / Pages
    win["-PAGE-"].update(values=page_codes)
    win["-PAGE_NAME-"].update(values=page_names)

    return matrix_rows

def edit_pages(win, matrix_rows):
    _, _, page_names, _ = build_catalog_from_matrix(matrix_rows)

    layout = [
        [sg.Text("Renomme une page Facebook")],
        [sg.Listbox(page_names, key="-PLIST-", size=(40, 8), enable_events=True)],
        [sg.Text("Nouveau nom"), sg.Input(key="-PNEW-")],
        [sg.Button("Renommer"), sg.Button("Fermer")],
    ]
    dlg = sg.Window("Pages FB", layout, modal=True)

    while True:
        ev, vals = dlg.read()
        if ev in (sg.WINDOW_CLOSED, "Fermer"):
            break

        if ev == "-PLIST-":
            if vals["-PLIST-"]:
                dlg["-PNEW-"].update(vals["-PLIST-"][0])
            continue

        if ev == "Renommer":
            if not vals["-PLIST-"]:
                sg.popup_error("Choisis une page dans la liste.")
                continue

            old = vals["-PLIST-"][0]
            new = vals["-PNEW-"].strip()
            if not new:
                sg.popup_error("Saisis un nouveau nom.")
                continue

            for r in matrix_rows:
                if r.get("page_name") == old:
                    r["page_name"] = new

            _, _, page_names, _ = build_catalog_from_matrix(matrix_rows)
            dlg["-PLIST-"].update(page_names)
            sg.popup("Page renommée.")

    dlg.close()
    save_json(MATRIX, {"rows": matrix_rows})

    # Recharger toutes les valeurs Launcher
    _, page_codes, page_names = build_catalog_from_matrix(matrix_rows)

    win["-PAGE-"].update(values=page_codes)
    win["-PAGE_NAME-"].update(values=page_names)

    return matrix_rows


