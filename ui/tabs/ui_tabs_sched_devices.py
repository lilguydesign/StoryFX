# -*- coding: utf-8 -*-
import PySimpleGUI as sg

from scheduler import build_planning   # ton scheduler.py reste tel quel


def make_sched_tab():
    headings = [
        "Profil", "Système", "Engine",
        "Album intro", "Album multi",
        "Plateforme", "Count",
        "Heure base", "Offset", "Heure réelle",
        "Pays", "Page"
    ]


    data = build_planning()  # lit les JSON et calcule toutes les lignes

    total = 0
    # data = [Profil, Système, Engine, Album intro, Album multi, Plateforme, Count,
    #         Heure base, Offset, Heure réelle, Page, Page name, IG variant]
    for row in data:
        try:
            total += int(row[6])  # colonne Count (index 6 maintenant)
        except Exception:
            pass

    layout = [
        [sg.Text("Programmations calculées (d'après profiles / systems / matrix)")],
        [sg.Table(
            values=data,
            headings=headings,
            key="-SCHED-TABLE-",
            auto_size_columns=True,
            display_row_numbers=True,
            justification="left",
            num_rows=15,
            enable_events=False,
            expand_x=True,
            expand_y=True,
        )],
        [
            sg.Text("Total count:", size=(12, 1)),
            sg.Text(str(total), key="-SCHED-TOTAL-", size=(8, 1)),
        ],
        [
            sg.Button("↻ Rafraîchir", key="-SCHED-REFRESH-"),
            sg.Button("▶ Démarrer scheduler", key="-SCHED-START-", button_color=("white", "green")),
            sg.Button("■ Arrêter scheduler", key="-SCHED-STOP-", button_color=("white", "firebrick4")),
        ],
    ]

    return layout


def build_devices_tab():
    """
    Onglet Devices : gestion de la connexion ADB des téléphones.
    """
    layout = [
        [sg.Text("Connexion ADB des téléphones")],
        [
            sg.Button("📡 Scanner & connecter", key="-DEV_SCAN_CONNECT-"),
            sg.Button("adb devices", key="-DEV_LIST-"),
            sg.Button("Copier serial(s)", key="-DEV_COPY_SERIAL-"),
            sg.Button("Connecter tout", key="-DEV_CONNECT_ALL-"),
            sg.Button("Déconnecter tout", key="-DEV_DISCONNECT-"),
            sg.Button("Effacer", key="-DEV_CLEAR-"),
        ],
        [
            sg.Multiline(
                key="-DEV_LOG-",
                size=(120, 25),       # terminal plus grand
                autoscroll=True,
                expand_x=True,
                expand_y=True,
                font=("Consolas", 9),  # police monospace agréable
            )
        ],
    ]
    return layout
