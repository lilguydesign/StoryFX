# ui/ui_paths_helpers.py
# -*- coding: utf-8 -*-
"""
Module centralisé de StoryFX pour :
    - Chemins principaux
    - Chargement / sauvegarde JSON
    - Chargement des albums / profils / systems / matrix
    - Construction du catalogue albums / pays / pages
    - Gestion ADB (path + environnement)
    - append_log (multiline LOG)
    - Helpers divers utilisés par l’UI et le Runner

Ce fichier récupère 100% de ce que app.py utilisait auparavant.
"""

import sys
import json
import subprocess
from pathlib import Path
import os
import re


# ==========================================================================
# 🔥 1. CHEMINS PRINCIPAUX
# ==========================================================================
HERE    = Path(__file__).resolve().parent        # .../StoryFx/ui
ROOT    = HERE.parent                            # .../StoryFx
CONFIG  = ROOT / "config"

RUNNER   = ROOT / "runner.py"
PROFILES = CONFIG / "profiles.json"
SYSTEMS  = CONFIG / "systems.json"
MATRIX   = CONFIG / "matrix.json"
ALBUMS   = CONFIG / "albums.json"

# Fichier de sauvegarde UI
UI_STATE = ROOT / "ui_state.json"

# Locators (XPaths)
LOCATORS = ROOT / "locators.json"


# ==========================================================================
# 🔥 2. ADB CONFIGURATION
# ==========================================================================

# Chemin ADB StoryFX (version stable utilisée par toute l’UI)
ADB_PATH = r"C:\Tools\ADB_StoryFX\adb.exe"

# ADB doit tourner sur port 5038 (pas de conflit avec runner)
ADB_ENV = os.environ.copy()
ADB_ENV["ANDROID_ADB_SERVER_PORT"] = "5038"


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def strip_ansi(s: str) -> str:
    """Supprime les codes couleurs ANSI (Appium, HTTP, etc.) d'une ligne."""
    return ANSI_RE.sub("", s)

def adb_run(cmd: str, port: int | None = None):
    """
    Exécute une commande ADB :
        - Remplace "adb" par ADB_PATH
        - Force env sur le port (par défaut 5038)
        - Retourne (code, sortie)
    """
    try:
        cmd = cmd.strip()

        if cmd.startswith("adb "):
            cmd = f"\"{ADB_PATH}\" {cmd[4:]}"
        elif cmd == "adb":
            cmd = f"\"{ADB_PATH}\""

        # ✅ port ADB : par défaut 5038 (StoryFX), sinon override
        env = os.environ.copy()
        if port is None:
            env.update(ADB_ENV)  # garde ton 5038 par défaut
        else:
            env["ANDROID_ADB_SERVER_PORT"] = str(port)

        proc = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        return proc.returncode, proc.stdout

    except Exception as e:
        return 1, str(e)

# ==========================================================================
# 🔥 3. JSON LOAD & SAVE HELPER
# ==========================================================================
def load_json(path: Path, default=None):
    """Lecture JSON sûre."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def save_json(path: Path, data):
    """Écriture JSON avec indentation lisible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==========================================================================
# 🔥 4. ALBUMS (intro / multi)
# ==========================================================================
def load_albums_dict():
    """
    Retourne :
        {album_name: {kind, album_size, count_per_post}}
    """
    albums = {}
    try:
        data = load_json(ALBUMS, {"albums": []})
    except Exception:
        data = {"albums": []}

    for row in data.get("albums", []):
        name = row.get("name")
        if not name:
            continue

        albums[name] = {
            "kind": row.get("kind", "multi"),
            "album_size": int(row.get("album_size", 0) or 0),
            "count_per_post": int(row.get("count_per_post", 0) or 0),
        }

    return albums


def save_albums_dict(albums: dict):
    rows = []
    for name, cfg in albums.items():
        rows.append({
            "name": name,
            "kind": cfg.get("kind", "multi"),
            "album_size": int(cfg.get("album_size", 0) or 0),
            "count_per_post": int(cfg.get("count_per_post", 0) or 0),
        })
    save_json(ALBUMS, {"albums": rows})


# Chargement initial pour construire les listes intro/multi
_albums_cfg = load_albums_dict()

INTRO_ALBUM_CHOICES = sorted(
    name for name, cfg in _albums_cfg.items()
    if cfg.get("kind", "multi") == "intro"
)

MULTI_ALBUM_CHOICES = sorted(
    name for name, cfg in _albums_cfg.items()
    if cfg.get("kind", "multi") == "multi"
)


# ==========================================================================
# 🔥 5. UI STATE (profil, engine, albums…)
# ==========================================================================
def load_ui_state():
    """Charge ui_state.json si présent."""
    return load_json(UI_STATE, {})


def save_ui_state(state: dict):
    """Sauvegarde ui_state.json."""
    save_json(UI_STATE, state)


# ==========================================================================
# 🔥 6. LOCATORS (XPaths)
# ==========================================================================
def load_locators_dict():
    return load_json(LOCATORS, {})


def save_locators_dict(data: dict):
    save_json(LOCATORS, data)


# ==========================================================================
# 🔥 7. PROFILS / SYSTEMS / MATRIX
# ==========================================================================
def load_profiles_dict():
    return load_json(PROFILES, {"profiles": {}}).get("profiles", {})


def load_systems_dict():
    return load_json(SYSTEMS, {"systems": {}}).get("systems", {})


def load_matrix_rows():
    return load_json(MATRIX, {"rows": []}).get("rows", [])


# ==========================================================================
# 🔥 8. BUILD DEVICES MAP
# ==========================================================================
def build_devices_map_from_profiles(profiles_dict: dict) -> dict:
    """
    Construit un mapping :
        adb_serial → {ip, port, label}

    Utilisé dans l’onglet Devices et lors de connexions ciblées.
    """
    devices_map = {}

    for prof_name, cfg in profiles_dict.items():
        adb_serial = cfg.get("adb_serial")
        ip        = cfg.get("tcpip_ip")
        port      = cfg.get("tcpip_port")
        label     = cfg.get("label", prof_name)

        if not adb_serial or not ip or not port:
            continue

        devices_map[adb_serial] = {
            "ip": str(ip),
            "port": str(port),
            "label": label,
        }

    return devices_map


# ==========================================================================
# 🔥 9. CATALOG : albums, pays, pages Facebook
# ==========================================================================
def build_catalog_from_matrix(matrix_rows):
    """
    Retourne :
        albums[], pages[], page_names[]
    Utilisé pour :
        - Combos Launcher
        - Combo Albums
        - Combo Matrix
    """

    albums_set = set()

    for row in matrix_rows:
        a1 = row.get("album")
        a2 = row.get("album2")

        if a1:
            albums_set.add(a1)
        if a2:
            albums_set.add(a2)

    albums = sorted(albums_set)

    page_codes  = sorted({row.get("page", "") for row in matrix_rows if row.get("page")})
    page_names  = sorted({row.get("page_name", "") for row in matrix_rows if row.get("page_name")})

    if not albums:
        albums = [""]

    return albums, page_codes, page_names

# ==========================================================================
# 🔥 10. APPEND LOG (Multiline)
# ==========================================================================
def append_log(win, msg: str):
    """
    Ajoute proprement une ligne de log dans -LOG-.
    win : sg.Window
    msg : texte à ajouter
    """
    try:
        win["-LOG-"].update(value=msg.rstrip() + "\n", append=True)
    except:
        pass


# ==========================================================================
# 🔥 11. PYTHON PATH
# ==========================================================================
def get_python_exe():
    """Retourne l'exécutable Python utilisé actuellement."""
    return sys.executable or "python"
