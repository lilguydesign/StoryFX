"""Legacy manual catch-up entry point; invoked only by the existing launcher."""
import os
import sys
from datetime import datetime
from legacy_scheduler_config import BASE_DIR, PROFILES_PATH, PROJECT_NAME, load_configs, run_cmd, write_clock_state
from legacy_scheduler_plan import iter_jobs

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
