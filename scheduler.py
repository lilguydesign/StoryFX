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
from legacy_scheduler_config import (write_clock_state, load_json, hhmm_add_offset, run_cmd, load_clock_state, get_logical_minute, load_configs, to_minutes, normalize_span)
from legacy_scheduler_plan import iter_jobs, build_planning
from legacy_scheduler_catchup import run_manual_catchup

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

# ---------- Utils JSON ----------

# ---------- Chargement / planning ----------

# --- Convertit HH:MM en minutes absolues + gestion du passage minuit ---

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
    try:
        ensure_appium_running()
    except Exception as e:
        print(f"[{PROJECT_NAME}] [WARN] Appium pas prêt au boot: {e}")
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

            # # --- EXÉCUTER LE JOB ---
            # ensure_appium_running()  # ← ajoute ceci ici

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
