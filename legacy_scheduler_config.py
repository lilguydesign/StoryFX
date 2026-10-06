"""Legacy scheduler configuration, virtual clock and command helper; no background start."""
import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, List

PROJECT_NAME = "StoryFX"
BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
PROFILES_PATH = CONFIG_DIR / "profiles.json"
SYSTEMS_PATH = CONFIG_DIR / "systems.json"
MATRIX_PATH = CONFIG_DIR / "matrix.json"
ALBUMS_PATH = CONFIG_DIR / "albums.json"
CLOCK_PATH = CONFIG_DIR / "scheduler_clock.json"

def write_clock_state(mode: str, hhmm: str | None = None):
    """
    Sauvegarde le mode de temps dans config/scheduler_clock.json.
    """
    data = {"mode": mode}
    if mode == "manual" and hhmm:
        data["time"] = hhmm

    try:
        CLOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CLOCK_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Scheduler] Erreur write_clock_state : {e}")


def load_json(path: Path) -> dict:
    """Charge un fichier JSON en UTF‑8, ou {} si problème."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[{PROJECT_NAME}] ⚠ Erreur lecture {path.name}: {e}")
        return {}


def hhmm_add_offset(hhmm: str, minutes: int) -> str:
    """Ajoute un décalage (en minutes) à une heure HH:MM."""
    try:
        h, m = map(int, hhmm.split(":"))
        t = datetime(2000, 1, 1, h, m) + timedelta(minutes=minutes)
        return f"{t.hour:02d}:{t.minute:02d}"
    except Exception:
        # Fallback si format inattendu
        return hhmm


def run_cmd(cmd_list: List[str]) -> None:
    """Exécute une commande système de manière fiable (sans shell=True)."""
    try:
        subprocess.run(cmd_list, check=False)
    except Exception as e:
        print(f"[{PROJECT_NAME}] ⚠ Erreur lors de l'exécution de la commande : {e}")


def load_clock_state() -> dict:
    """
    Charge le mode de temps du scheduler.

    Format attendu dans config/scheduler_clock.json :

      {"mode": "auto"}
    ou
      {"mode": "manual", "time": "13:00"}   # heure virtuelle HH:MM en 24h

    Si le fichier n'existe pas ou est invalide → mode auto.
    """
    if not CLOCK_PATH.exists():
        return {"mode": "auto"}

    try:
        with CLOCK_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"mode": "auto"}

        mode = data.get("mode", "auto")
        if mode not in ("auto", "manual"):
            mode = "auto"

        hhmm = data.get("time")
        if not isinstance(hhmm, str):
            hhmm = None

        return {"mode": mode, "time": hhmm}
    except Exception:
        # En cas de souci, on repasse en auto
        return {"mode": "auto"}


def get_logical_minute() -> str:
    """
    Retourne la minute logique HH:MM utilisée par le scheduler.

    - mode auto   → heure réelle du PC
    - mode manual → horloge virtuelle qui démarre à 'time'
                    puis avance d'1 minute pour chaque minute réelle.
    """
    # Initialisation des attributs "statiques" de la fonction
    if not hasattr(get_logical_minute, "_logical_time"):
        get_logical_minute._logical_time = None   # datetime virtuelle
        get_logical_minute._last_real = None      # dernière heure réelle lue
        get_logical_minute._last_state = None     # (mode, hhmm) pour détecter les changements

    state = load_clock_state()
    mode = state.get("mode", "auto")
    hhmm = (state.get("time") or "").strip()

    # ----- MODE AUTO : on utilise l'heure du PC, et on reset l'horloge virtuelle -----
    if mode != "manual":
        get_logical_minute._logical_time = None
        get_logical_minute._last_real = None
        get_logical_minute._last_state = None
        return datetime.now().strftime("%H:%M")

    # ----- MODE MANUEL : horloge virtuelle -----
    key = (mode, hhmm)

    # (1) Première fois, ou bien l'utilisateur a changé l'heure manuelle :
    #     on ré-initialise l'horloge virtuelle à hh:mm
    if get_logical_minute._logical_time is None or get_logical_minute._last_state != key:
        try:
            h_str, m_str = hhmm.split(":")
            h = int(h_str)
            m = int(m_str)
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
        except Exception:
            # si l'heure dans le JSON est cassée, on part sur l'heure PC
            now = datetime.now()
            h, m = now.hour, now.minute

        get_logical_minute._logical_time = datetime(2000, 1, 1, h, m)
        get_logical_minute._last_real = datetime.now()
        get_logical_minute._last_state = key

    else:
        # (2) On fait avancer l'horloge virtuelle selon le temps réel écoulé
        now_real = datetime.now()
        delta = now_real - get_logical_minute._last_real
        secs = int(delta.total_seconds())

        if secs >= 60:
            minutes = secs // 60
            get_logical_minute._logical_time += timedelta(minutes=minutes)
            get_logical_minute._last_real += timedelta(seconds=minutes * 60)

    t = get_logical_minute._logical_time
    return f"{t.hour:02d}:{t.minute:02d}"


def load_configs() -> Tuple[dict, dict, dict, dict]:
    """Charge profiles / systems / matrix à partir du dossier config."""
    profiles = load_json(PROFILES_PATH)
    systems  = load_json(SYSTEMS_PATH)
    matrix   = load_json(MATRIX_PATH)
    albums   = load_json(ALBUMS_PATH)
    return profiles, systems, matrix, albums


def to_minutes(hhmm: str) -> int:
    """Retourne un entier minutes, compatible cross-journée.

    Exemple :
        - Maintenant = 00:48 (48)
        - Heure de départ = 15:00 → doit devenir 15:00 de la veille ⇒ 15*60 - 24*60 = -540
    """
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def normalize_span(start_min: int, real_min: int) -> Tuple[int, int]:
    """Corrige le passage minuit entre START et REAL.

    Exemple :
        start = 15:00 → 900
        real = 00:48 → 48
    ⇒ Le scheduler doit comprendre : start = 900 - 1440 = -540
    """
    if real_min < start_min:
        # passage dans la nuit → décaler start au jour précédent
        start_min -= 1440
    return start_min, real_min
