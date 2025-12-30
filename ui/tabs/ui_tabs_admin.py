
# en haut du fichier
from collections import Counter
import PySimpleGUI as sg

from ui.ui_paths_helpers import (
    INTRO_ALBUM_CHOICES,
    MULTI_ALBUM_CHOICES,
    load_systems_dict,
    load_profiles_dict,
    build_catalog_from_matrix,
)

from pathlib import Path
import json

PAGES_FILE = Path(__file__).resolve().parents[2] / "config" / "pages.json"

def _load_pages_from_json():
    """Charge la liste des pages depuis config/pages.json."""
    pages = []
    if PAGES_FILE.exists():
        with PAGES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        pages = data.get("pages", [])
    return pages

def build_pages_tab():
    """Onglet Admin pour gérer les pages Facebook (Pays + Page)."""
    pages = _load_pages_from_json()
    data = [
        [p.get("country", ""), p.get("name", "")]
        for p in pages
    ]

    headings = ["Pays", "Page"]

    table = sg.Table(
        values=data,
        headings=headings,
        key="-PG_TABLE-",
        enable_events=True,
        auto_size_columns=True,
        justification="left",
        expand_x=True,
        expand_y=True,
        num_rows=10,
        display_row_numbers=True,
    )

    layout = [
        [table],
        [
            sg.Text("Pays"),
            sg.Input(key="-PG_COUNTRY-", size=(20, 1)),

            sg.Text("Page"),
            sg.Input(key="-PG_NAME-", size=(30, 1)),
        ],
        [
            sg.Button("Ajouter", key="-PG_ADD-"),
            sg.Button("Mettre à jour", key="-PG_UPDATE-"),
            sg.Button("Supprimer", key="-PG_DEL-"),
        ],
    ]
    return layout


def refresh_pages_table(win):
    """Recharge la table des pages depuis pages.json."""
    pages = _load_pages_from_json()
    data = [
        [p.get("country", ""), p.get("name", "")]
        for p in pages
    ]
    win["-PG_TABLE-"].update(values=data)


def build_profiles_tab():
    headings = [
        "enabled",     # 🟩 nouvelle colonne
        "name",
        "device_id",
        "adb_serial",
        "tcpip_ip",
        "tcpip_port",
        "platform_version",
        "offset_minutes",
        "rows",
    ]

    table = sg.Table(
        headings=headings,
        values=[],
        key="-PROF_TABLE-",
        auto_size_columns=True,
        display_row_numbers=True,  # ✅ indice
        select_mode=sg.TABLE_SELECT_MODE_EXTENDED,  # ✅ multi-select
        enable_events=True,
        expand_x=True,
        expand_y=True,
        justification="center",
    )

    sort_row = [
        sg.Text("Trier par"),
        sg.Combo(
            ["enabled", "name", "device_id", "adb_serial", "tcpip_ip", "tcpip_port",
             "platform_version", "offset_minutes", "rows"],
            key="-P_SORT_KEY-",
            default_value="name",
            readonly=True,
            size=(16, 1),
        ),
        sg.Checkbox("A→Z", key="-P_SORT_ASC-", default=True),
        sg.Button("Trier", key="-P_SORT-"),
    ]

    # 🔥 LIGNE 1 — on met le bouton Coller juste après adb_serial
    bottom_row1 = [
        sg.Text("name"),
        sg.Input(key="-P_NAME-", size=(12, 1)),
        sg.Input("", key="-P_NAME_ORIG-", visible=False),

        sg.Text("device_id"),
        sg.Input(key="-P_DEVICE-", size=(18, 1)),

        sg.Text("adb_serial"),
        sg.Input(key="-P_ADB_SERIAL-", size=(14, 1)),
        sg.Checkbox("Propager serial", key="-P_PROP_SERIAL-", default=False),
        sg.Button("Coller serial", key="-P_PASTE_SERIAL-"),   # 🆕 déplacé ici !
    ]

    # LIGNE 2 (inchangée)
    bottom_row2 = [
        sg.Text("tcpip_ip"),
        sg.Input(key="-P_TCPIP_IP-", size=(14, 1)),

        sg.Text("port"),
        sg.Input(key="-P_TCPIP_PORT-", size=(6, 1)),

        sg.Text("platform_version"),
        sg.Input(key="-P_PVER-", size=(4, 1)),

        sg.Text("offset"),
        sg.Input(key="-P_OFFSET-", size=(4, 1)),
        sg.Checkbox("Actif", key="-P_ENABLED-", default=True),

        sg.Button("Add / Update", key="-P_SAVE-"),
        sg.Button("Supprimer", key="-P_DEL-"),
    ]

    # LIGNE 3 — On garde seulement Rafraîchir
    bottom_row3 = [
        sg.Button("Dupliquer", key="-P_DUP-"),  # 🆕
        sg.Button("Rafraîchir", key="-P_REFRESH-"),
    ]

    bottom_row4 = [
        sg.Text("appium_overrides (JSON)"),
        sg.Multiline(
            "",
            key="-P_APPIUM_OVERRIDES-",
            size=(80, 4),
            font=("Consolas", 9),
        ),
    ]

    bottom_row5 = [
        sg.Text("Gallery appPackage"),
        sg.Input(key="-P_GALLERY_PKG-", size=(35, 1)),
        sg.Text("Gallery appActivity"),
        sg.Input(key="-P_GALLERY_ACT-", size=(45, 1)),
    ]

    layout = [
        [table],
        sort_row,  # ✅ nouveau
        bottom_row1,
        bottom_row2,
        bottom_row3,
        bottom_row4,
        bottom_row5,
    ]

    return layout


def build_systems_tab():
    headings = ["key", "times (HH:MM,HH:MM,...)"]
    layout = [
        [
            sg.Table(
                values=[],
                headings=headings,
                key="-SYS_TABLE-",
                enable_events=True,
                auto_size_columns=True,
                justification="left",
                expand_x=True,
                expand_y=True,
                num_rows=8,
            )
        ],
        [
            sg.Text("key"),
            sg.Input(key="-S_KEY-", size=(20, 1)),
            sg.Input("", key="-S_KEY_ORIG-", visible=False),  # 👈 ancien nom caché

            sg.Text("times"),
            sg.Input(key="-S_TIMES-", size=(40, 1)),
        ],
        [
            sg.Button("Add", key="-S_ADD-"),
            sg.Button("Update", key="-S_UPDATE-"),
            sg.Button("Supprimer", key="-S_DEL-"),
        ],
    ]
    return layout

def build_matrix_tab():
    headings = [
        "device", "system", "engine",
        "album_intro", "album_multi",
        "album_size", "count",
        "platform", "pays", "page_name",
    ]

    # 🔥 Charger les pays/pages depuis config/pages.json
    pages_file = Path(__file__).resolve().parents[2] / "config" / "pages.json"
    countries, page_names = [], []

    if pages_file.exists():
        with pages_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("pages", []):
            c = (entry.get("country") or "").strip()
            n = (entry.get("name") or "").strip()
            if c:
                countries.append(c)
            if n:
                page_names.append(n)

    countries = sorted(set(countries))
    page_names = sorted(set(page_names))

    layout = [
        [
            sg.Table(
                values=[],
                headings=headings,
                key="-MAT_TABLE-",
                enable_events=True,
                auto_size_columns=True,
                justification="left",
                expand_x=True,
                expand_y=True,
                num_rows=12,
                display_row_numbers=True,
                select_mode=sg.TABLE_SELECT_MODE_EXTENDED,  # ✅ multi-sélection
            )
        ],
        [
            sg.Text("Total count:", size=(10, 1)),
            sg.Text("0", key="-MAT_TOTAL-", size=(6, 1)),
        ],
        [
            sg.Text("Trier par"),
            sg.Combo(
                ["device", "system", "engine", "album intro", "album multi", "platform", "pays", "page_name", "count"],
                key="-M_SORT_KEY-",
                default_value="device",
                readonly=True,
                size=(14, 1),
            ),
            sg.Checkbox("A→Z", key="-M_SORT_ASC-", default=True),
            sg.Button("Trier", key="-M_SORT-"),
        ],

        [
            sg.Text("device"),
            sg.Combo([], key="-M_DEVICE-", size=(12, 1), readonly=True, enable_events=True),

            sg.Text("system"),
            sg.Combo([], key="-M_SYSTEM-", size=(16, 1), readonly=True),

            sg.Text("engine"),
            sg.Combo(
                ["intro", "multi", "intro+multi"],
                key="-M_ENGINE-", size=(10, 1),
                readonly=True, default_value="multi",
            ),

            sg.Text("platform"),
            sg.Combo(
                ["WhatsApp", "Facebook", "Instagram", "TikTok"],
                key="-M_PLATFORM-", size=(12, 1),
                readonly=True, default_value="WhatsApp",
            ),
        ],

        [
            sg.Text("album intro"),
            sg.Combo(
                INTRO_ALBUM_CHOICES, key="-M_ALBUM-",
                size=(20, 1), readonly=True,
            ),

            sg.Text("album multi"),
            sg.Combo(
                MULTI_ALBUM_CHOICES, key="-M_ALBUM2-",
                size=(22, 1), readonly=True,
            ),

            sg.Text("album_size"),
            sg.Input(key="-M_ALBUM_SIZE-", size=(6, 1), default_text="0"),

            sg.Text("count"),
            sg.Input(key="-M_COUNT-", size=(5, 1), default_text="11"),
        ],

        [
            sg.Text("Pays"),
            sg.Combo(countries, key="-M_PAGE-", size=(25, 1), readonly=True),

            sg.Text("Page"),
            sg.Combo(page_names, key="-M_PNAME-", size=(40, 1), readonly=True),
        ],

        [
            sg.Button("Rafraîchir (Albums -> Matrix)", key="-M_REFRESH-"),
            sg.Button("Add row", key="-M_ADD-"),
            sg.Button("Update row", key="-M_UPDATE-"),
            sg.Button("Supprimer row", key="-M_DEL-"),
            sg.Button("Dupliquer row", key="-M_DUP-"),
        ],
    ]

    return layout


# ---------- Refresh des tables ----------
def refresh_profiles_table(win, profiles: dict, matrix_rows: list):
    """
    Recharge la table des profils avec :
    - colonnes ADB (serial, ip, port)
    - nb de lignes Matrix par profil (colonne 'device')
    """
    # Compter les lignes Matrix par profil
    counts = Counter()
    for r in matrix_rows or []:
        dev = r.get("device")
        if dev:
            counts[dev] += 1

    data = []
    names = getattr(win, "_prof_view_names", None) or sorted(profiles.keys())

    for name in names:
        cfg = profiles.get(name, {})
        device_id       = cfg.get("device_id", "")
        adb_serial      = cfg.get("adb_serial", "")
        tcpip_ip        = cfg.get("tcpip_ip", "")
        tcpip_port      = cfg.get("tcpip_port", "")
        platform_version = cfg.get("platform_version", "")
        offset          = cfg.get("offset_minutes", 0)
        row_count       = counts.get(name, 0)
        enabled = cfg.get("enabled", True)
        enabled_icon = "🟢" if enabled else "🔴"
        data.append([
            enabled_icon,  # 🔥 1ère colonne = état activé/désactivé
            name,
            device_id,
            adb_serial,
            tcpip_ip,
            tcpip_port,
            platform_version,
            offset,
            row_count,
        ])

    win["-PROF_TABLE-"].update(values=data)
    try:
        win["-M_DEVICE-"].update(values=sorted(profiles.keys()))
    except Exception:
        pass

sg.Checkbox("Propager serial", key="-P_PROP_SERIAL-", default=False),

def refresh_systems_table(win, systems):
    data = []
    keys_sorted = sorted(systems.keys())

    # Table Systems
    for key in keys_sorted:
        val = systems[key]
        if isinstance(val, list):
            times = val
        else:
            times = val.get("times", [])
        data.append([key, ",".join(times)])

    win["-SYS_TABLE-"].update(values=data)

    # 🔥 Propagation vers les autres onglets

    # 1) Onglet Albums : combo System
    try:
        win["-ALB_SYSTEM-"].update(values=keys_sorted)
    except Exception:
        pass  # au cas où l'onglet n'est pas encore construit

    # 2) Onglet Matrix : combo System
    try:
        win["-M_SYSTEM-"].update(values=keys_sorted)
    except Exception:
        pass



def refresh_matrix_table(win, matrix_rows):
    data = []
    total_count = 0
    for r in matrix_rows:
        c = r.get("count", 0) or 0
        try:
            total_count += int(c)
        except Exception:
            pass

        data.append([
            r.get("device", ""),
            r.get("system", ""),
            r.get("engine", ""),
            r.get("album", ""),
            r.get("album2", ""),
            r.get("album_size", ""),
            c,
            r.get("platform", "WhatsApp"),
            r.get("page", ""),        # ici = Pays
            r.get("page_name", ""),   # ici = Nom de la page
        ])

    win["-MAT_TABLE-"].update(values=data)
    win["-MAT_TOTAL-"].update(str(total_count))

    # # 🔥 Mettre à jour la liste des pays / pages pour les combos Matrix
    # try:
    #     _, page_codes, page_names = build_catalog_from_matrix(matrix_rows)
    #     win["-M_PAGE-"].update(values=page_codes)
    #     win["-M_PNAME-"].update(values=page_names)
    # except Exception:
    #     pass


def build_albums_tab():
    headings = [
        "name",
        "engine",
        "album_size",
        "count_per_post",
        "scroll_max",
        "system",
        "engine_full",
        "intro_album",
        "profiles",
    ]


    table = sg.Table(
        values=[],
        headings=headings,
        key="-ALB_TABLE-",
        enable_events=True,
        auto_size_columns=True,
        justification="center",
        expand_x=True,
        expand_y=True,
        num_rows=8,
    )

    layout = [
        [table],

        # Ligne 1 : infos de base de l'album
        [
            sg.Text("name"),
            # readonly=False pour pouvoir taper un nouveau nom
            sg.Combo(values=[], key="-ALB_NAME-", size=(22, 1), readonly=False),
            sg.Input("", key="-ALB_NAME_ORIG-", visible=False),  # ancien nom (invisible)

            sg.Text("engine"),
            sg.Combo(
                values=["intro", "multi"],
                key="-ALB_KIND-",
                size=(8, 1),
                default_value="multi",
            ),

            sg.Text("album_size"),
            sg.Input(key="-ALB_SIZE-", size=(6, 1)),

            sg.Text("count/post"),
            sg.Input(key="-ALB_COUNT-", size=(6, 1)),
        ],

        # Ligne 2 : boutons CRUD
        [
            sg.Button("Nouveau", key="-ALB_NEW-"),
            sg.Button("Add / Update", key="-ALB_SAVE-"),
            sg.Button("Supprimer", key="-ALB_DEL-"),
            sg.Button("Sync counts -> Matrix", key="-ALB_SYNC-"),
            sg.Button("Sync -> profils", key="-ALB_PUSH_ALL-"),
        ],

        # Ligne 3 : sélection multi-profils + system
        [
            sg.Text("Profils"),
            sg.Listbox(
                values=[],
                key="-ALB_DEVICES-",
                select_mode=sg.SELECT_MODE_EXTENDED,  # plusieurs profils possibles
                size=(22, 4),
            ),
            sg.Button("Tous", key="-ALB_SELECT_ALL_PROF-"),  # 👈 nouveau bouton

            sg.Text("System"),
            sg.Combo(
                [],
                key="-ALB_SYSTEM-",
                size=(20, 1),
                readonly=True,
            ),
        ],

        # Ligne 4 : engine complet + album intro
        [
            sg.Text("Engine complet"),
            sg.Combo(
                ["intro", "multi", "intro+multi"],
                key="-ALB_ENGINE_FULL-",
                size=(12, 1),
                default_value="multi",
            ),

            sg.Text("Album intro (si intro+multi)"),
            sg.Combo(
                [],
                key="-ALB_INTRO_TMP-",
                size=(22, 1),
                readonly=True,
            ),
        ],
    ]

    return layout

def refresh_albums_table(win, albums_dict):
    import math

    data = []
    names = sorted(albums_dict.keys())
    for name in names:
        cfg = albums_dict[name]
        size = cfg.get("album_size", 0)
        scroll_max = 3
        if size > 0:
            scroll_max = max(1, min(10, math.ceil(size / 250.0)))

        profiles_list = cfg.get("profiles", []) or []
        profiles_str = " | ".join(profiles_list)

        data.append([
            name,
            cfg.get("kind", "multi"),
            size,
            cfg.get("count_per_post", 0),
            scroll_max,
            cfg.get("default_system", ""),
            cfg.get("engine_full", ""),
            cfg.get("intro_album", ""),
            profiles_str,
        ])

    # Rafraîchir la table + combo name
    win["-ALB_TABLE-"].update(values=data)
    win["-ALB_NAME-"].update(values=names)

    # ---------- Nouveaux éléments : systems, profils, albums intro ----------

    # Systems
    systems_raw = load_systems_dict()
    if isinstance(systems_raw, dict) and "systems" in systems_raw:
        systems = systems_raw["systems"]
    else:
        systems = systems_raw or {}

    win["-ALB_SYSTEM-"].update(values=sorted(systems.keys()))

    # Profils actifs
    profiles_raw = load_profiles_dict()
    if isinstance(profiles_raw, dict) and "profiles" in profiles_raw:
        profiles = profiles_raw["profiles"]
    else:
        profiles = profiles_raw or {}

    # Profils (actifs + inactifs)
    profile_names = sorted(profiles.keys())
    win["-ALB_DEVICES-"].update(values=profile_names)

    # Albums intro (pour intro+multi)
    intro_albums = sorted(
        n for n, c in albums_dict.items()
        if c.get("kind", "multi") == "intro"
    )
    win["-ALB_INTRO_TMP-"].update(values=intro_albums)
