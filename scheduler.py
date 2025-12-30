# -*- coding: utf-8 -*-
"""
StoryFX Scheduler
-----------------
- Lit profiles.json, systems.json, matrix.json
- Applique l'offset de chaque profil aux heures de base
- Déclenche runner.py avec:
    --profile, --engine, --album, [--count]
    --platform, [--page], [--page_name]
- Anti double-lancement: un job ne part qu'une fois par minute.

En plus:
- build_planning() : renvoie la liste complète des programmations
  (utile pour l'onglet "Programmation" du front-end).
"""
import os
import json
import time
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Dict, Any, List, Tuple
from ui.ui_devices import ensure_appium_running

RATTRAPAGE_DONE = False
PROJECT_NAME = "StoryFX"  # anciennement WA-HUB

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "config"
PROFILES_PATH = CONFIG_DIR / "profiles.json"
SYSTEMS_PATH = CONFIG_DIR / "systems.json"
MATRIX_PATH = CONFIG_DIR / "matrix.json"
ALBUMS_PATH   = CONFIG_DIR / "albums.json"   # 🆕
CLOCK_PATH   = CONFIG_DIR / "scheduler_clock.json"  # 🆕 mode auto / manuel

# --- Gestion écriture heure scheduler_clock.json ---
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


# ---------- Utils JSON ----------

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

# ---------- Chargement / planning ----------

def load_configs() -> Tuple[dict, dict, dict, dict]:
    """Charge profiles / systems / matrix à partir du dossier config."""
    profiles = load_json(PROFILES_PATH)
    systems  = load_json(SYSTEMS_PATH)
    matrix   = load_json(MATRIX_PATH)
    albums   = load_json(ALBUMS_PATH)
    return profiles, systems, matrix, albums


def iter_jobs(profiles: dict, systems: dict, matrix: dict, albums: dict) -> Iterator[Dict[str, Any]]:
    """
    Génère toutes les programmations possibles.

    Un job contient maintenant :
      - album_intro : album d'intro (engine intro / intro+multi)
      - album_multi : album multi (engine multi / intro+multi)
      - count       : nombre d'images, dérivé de albums.json quand c'est du multi
    """
    # On prépare un dict {nom_album: config_album} pour aller vite
    albums_dict = {a.get("name"): a for a in albums.get("albums", [])}

    for dev_name, dev in profiles.get("profiles", {}).items():
        if not dev.get("enabled", True):
            continue  # 🔥 Skip ce device

        offset = int(dev.get("offset_minutes", 0))

        for row in matrix.get("rows", []):
            if row.get("device") != dev_name:
                continue

            sys_key = row["system"]
            sys_conf = systems.get("systems", {}).get(sys_key)
            if sys_conf is None:
                print(f"[{PROJECT_NAME}] ⚠ Système '{sys_key}' introuvable dans systems.json.")
                continue

            # Compat : systems["systems"][key] peut être soit une liste,
            # soit un dict {"times": [...]}
            if isinstance(sys_conf, dict):
                times = sys_conf.get("times", [])
            else:
                times = sys_conf

            engine = row.get("engine") or ""
            album_intro = row.get("album")  or ""
            album_multi = row.get("album2") or ""
            raw_count   = row.get("count", 0) or 0
            platform    = row.get("platform", "WhatsApp")
            page        = row.get("page")
            page_name   = row.get("page_name")


            # --- Déterminer le count réel ---
            count = int(raw_count)
            # Pour multi et intro+multi, on essaie de prendre count_per_post de l'album multi
            if engine in ("multi", "intro+multi"):
                multi_name = album_multi or album_intro
                cfg = albums_dict.get(multi_name or "")
                if cfg:
                    c = cfg.get("count_per_post")
                    if c:
                        count = int(c)

            for base_time in times:
                t_effective = hhmm_add_offset(base_time, offset)
                yield {
                    "device": dev_name,
                    "system": sys_key,
                    "engine": engine,
                    "album_intro": album_intro,
                    "album_multi": album_multi,
                    "count": count,
                    "platform": platform,
                    "page": page,         # Pays
                    "page_name": page_name,  # Page
                    "base_time": base_time,
                    "offset_minutes": offset,
                    "time_effective": t_effective,
                }

def build_planning() -> List[List[str]]:
    """
    Construit un tableau lisible pour la GUI.
    Chaque ligne = [device, system, engine,
                    album_intro, album_multi,
                    platform, count, base_time,
                    offset, time_effective,
                    page, page_name, ig_variant]
    """
    profiles, systems, matrix, albums = load_configs()
    table: List[List[str]] = []

    for job in iter_jobs(profiles, systems, matrix, albums):
        table.append([
            job["device"],
            job["system"],
            job.get("engine") or "",
            job.get("album_intro") or "",
            job.get("album_multi") or "",
            job.get("platform") or "",
            str(job.get("count") or ""),
            job["base_time"],
            f"{job['offset_minutes']} min",
            job["time_effective"],
            job.get("page") or "",       # Pays
            job.get("page_name") or "",  # Nom de la page
        ])


    # Tri par heure effective puis device
    table.sort(key=lambda r: (r[9], r[0], r[1]))
    return table


def run_manual_catchup(state: dict) -> None:
    """
    Exécute TOUTES les programmations entre:
        start_time ≤ job_time ≤ heure réelle (au moment du test)
    Et refait autant de passes que nécessaire jusqu'à ne rater AUCUN job.
    """

    start_hhmm = state.get("time")
    if not start_hhmm:
        return

    start_min = int(start_hhmm.replace(":", ""))  # HHMM → int

    profiles, systems, matrix, albums = load_configs()

    # Pré-tri global des jobs selon leur time_effective
    all_jobs = sorted(
        iter_jobs(profiles, systems, matrix, albums),
        key=lambda j: j["time_effective"],
    )

    print(f"[{PROJECT_NAME}] Rattrapage manuel initial… point de départ = {start_hhmm}")

    already_run = set()  # éviter double exécution

    while True:
        now_hm = datetime.now().strftime("%H:%M")
        now_min = int(now_hm.replace(":", ""))

        print(f"[{PROJECT_NAME}] Fenêtre rattrapage : {start_hhmm} → {now_hm}")

        did_run_something = False

        for job in all_jobs:
            job_time = job["time_effective"]
            job_min = int(job_time.replace(":", ""))

            # Fenêtre dynamique :
            if not (start_min <= job_min <= now_min):
                continue

            # Déjà exécuté ?
            key = (job["device"], job["system"], job_min)
            if key in already_run:
                continue

            # ---- LANCEMENT DU JOB ----
            # Construire commande runner
            engine_ui = job["engine"] or ""
            engine_cli = "intro_multi" if engine_ui == "intro+multi" else engine_ui

            cmd = [
                sys.executable or "python",
                str(BASE_DIR / "runner.py"),
                "--profiles", str(PROFILES_PATH),
                "--profile", job["device"],
                "--engine", engine_cli,
                "--platform", job["platform"],
            ]

            if engine_cli == "intro":
                cmd += ["--album", job["album_intro"]]
            elif engine_cli == "multi":
                cmd += ["--album", job["album_multi"], "--count", str(job["count"])]
            elif engine_cli == "intro_multi":
                cmd += [
                    "--album", job["album_intro"],
                    "--album2", job["album_multi"],
                    "--count", str(job["count"]),
                ]

            if job.get("page"):
                cmd += ["--page", job["page"]]
            if job.get("page_name"):
                cmd += ["--page_name", job["page_name"]]


            timestamp = job_time + ":00"
            os.environ["STORYFX_TIME"] = timestamp

            print(
                f"[{PROJECT_NAME}] {timestamp} → Rattrapage : Lancement {job['device']} | "
                f"Sys={job['system']} | Plat={job['platform']} | Engine={engine_cli}"
            )
            print("   CMD:", " ".join(cmd))

            run_cmd(cmd)
            already_run.add(key)
            did_run_something = True

        # ---- FIN DE PASSE ----
        if not did_run_something:
            break   # plus rien à rattraper → 100% OK

        # On boucle encore une fois car de nouveaux jobs peuvent devenir éligibles
        print(f"[{PROJECT_NAME}] Vérification jobs supplémentaires…")

    # ---- SORTIE ----
    final_now = datetime.now().strftime("%H:%M")
    write_clock_state("auto", final_now)
    print(f"[{PROJECT_NAME}] Rattrapage terminé définitivement → retour auto ({final_now})")

# --- Convertit HH:MM en minutes absolues + gestion du passage minuit ---
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

# ---------- Boucle scheduler (mode "service") ----------

def scheduler_loop() -> None:
    """
    Boucle infinie :
      - calcule l'heure courante logique (auto ou manuel)
      - parcourt les jobs et déclenche ceux dont l'heure correspond
      - gère le rattrapage
      - transmet l'heure logique au runner via STORYFX_TIME
    """

    global RATTRAPAGE_DONE
    RATTRAPAGE_DONE = False

    # 🔥 Nouvelle version PRO : démarrage Appium (ADB StoryFX + attente)
    print("[StoryFX] Vérification Appium…")
    ensure_appium_running()
    print(f"[{PROJECT_NAME}] Scheduler prêt ✅")

    last_fired = set()


    while True:

        state = load_clock_state()
        mode = state.get("mode", "auto")

        # ---------------------------------------------------------
        # 🔥 1) RATTRAPAGE INITIAL AU LANCEMENT DU SCHEDULER
        # ---------------------------------------------------------
        if mode == "manual" and not RATTRAPAGE_DONE:
            run_manual_catchup(state)
            RATTRAPAGE_DONE = True

        # Heure réelle
        now_real = datetime.now().strftime("%H:%M")

        # Heure logique (auto ou manuel)
        logical_hm = get_logical_minute()

        # Heure affichée envoyée au runner
        if mode == "manual" and logical_hm < now_real:
            display_time = logical_hm + ":00"
        else:
            display_time = datetime.now().strftime("%H:%M:%S")

            if mode == "manual" and not RATTRAPAGE_DONE:
                print(f"[{PROJECT_NAME}] Rattrapage terminé → retour à l’heure réelle")
                RATTRAPAGE_DONE = True

        os.environ["STORYFX_TIME"] = display_time

        # Charger les données
        profiles, systems, matrix, albums = load_configs()

        # Conversion minutes (avec gestion minuit)
        logical_min = to_minutes(logical_hm)
        real_min = to_minutes(now_real)

        if mode == "manual":
            start_min = to_minutes(state["time"])
            start_min, real_min = normalize_span(start_min, real_min)

        # --- LANCEMENT DES JOBS ---
        for job in iter_jobs(profiles, systems, matrix, albums):

            job_hm = job["time_effective"]
            job_min = to_minutes(job_hm)

            # Gestion passage minuit job <-> start
            if mode == "manual" and job_min < start_min:
                job_min += 1440

            # --- LOGIQUE PRO du rattrapage ---
            if mode == "manual":

                # 1) JOB doit être dans [start_min → real_min]
                if not (start_min <= job_min <= real_min):
                    continue

                # 2) JOB lancé seulement quand logical == job
                if job_min != logical_min:
                    continue

            else:
                # MODE AUTO
                if job_hm != logical_hm:
                    continue

            # --- ANTI DOUBLE-LANCEMENT ---
            guard_key = (job_hm, job["device"], job["system"])
            if guard_key in last_fired:
                continue
            last_fired.add(guard_key)

            # --- EXÉCUTER LE JOB ---
            print(f"[{PROJECT_NAME}] {display_time} → Lancement {job['device']} | Sys={job['system']} | Plat={job['platform']}")

            # --- AVANT de construire la commande ---
            engine_ui = job["engine"] or ""
            engine_cli = "intro_multi" if engine_ui == "intro+multi" else engine_ui

            cmd = [
                sys.executable, str(BASE_DIR / "runner.py"),
                "--profiles", str(PROFILES_PATH),
                "--profile", job["device"],
                "--engine", engine_cli,
                "--platform", job["platform"],
            ]

            if engine_cli == "intro":
                cmd += ["--album", job["album_intro"]]
            elif engine_cli == "multi":
                cmd += ["--album", job["album_multi"], "--count", str(job["count"])]
            elif engine_cli == "intro_multi":
                cmd += [
                    "--album", job["album_intro"],
                    "--album2", job["album_multi"],
                    "--count", str(job["count"]),
                ]

            # --- EXÉCUTER LE JOB ---
            ensure_appium_running()  # ← ajoute ceci ici

            print(
                f"[{PROJECT_NAME}] {display_time} → Lancement {job['device']} | Sys={job['system']} | Plat={job['platform']}")

            run_cmd(cmd)

        # --- FIN RATTRAPAGE : BASCULE EN MODE AUTO ---
        if mode == "manual" and logical_min >= real_min:
            print(f"[{PROJECT_NAME}] Rattrapage terminé définitivement → retour auto")
            write_clock_state("auto", now_real)
            RATTRAPAGE_DONE = True

        time.sleep(1)

# ---------- Entrées CLI ----------

def main() -> None:
    """
    Mode console :
      python scheduler.py
    → lance la boucle infinie.
    """
    try:
        scheduler_loop()
    except KeyboardInterrupt:
        print(f"\n[{PROJECT_NAME}] Scheduler arrêté manuellement.")


if __name__ == "__main__":
    main()
