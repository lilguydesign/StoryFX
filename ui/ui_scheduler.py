# ui/ui_scheduler.py
# -*- coding: utf-8 -*-
"""
Module : Gestion complète du PROGRAMMATEUR (Scheduler UI)

Ce module extrait **toute la logique liée à la programmation** qui se trouvait dans app.py :
- Démarrage du scheduler (boucle infinie)
- Arrêt du scheduler
- Thread de lecture des logs
- Mise à jour UI (-SCHED-LOG-, -SCHED-DONE-)
- Rafraîchissement complet du planning (-SCHED-REFRESH-)
- Injection de STORYFX_TIME (heure logique) avant lancement du Runner
- Synchronisation Albums → Matrix (counts multi)
- Gestion des erreurs

Cette version est 100 % fidèle à ton code source original,
mais découpée PROPREMENT, prête à être utilisée dans app.py.
"""
import psutil   # À mettre en haut du fichier
import subprocess
import threading
import os

from ui.ui_paths_helpers import (
    ROOT,
    MATRIX,
    save_json,
    append_log,
    get_python_exe,
    strip_ansi,  # 👈 ajout
)
from scheduler import build_planning, get_logical_minute


# ==========================================================================
# 🔥 1) START SCHEDULER
# ==========================================================================
def start_scheduler(win, scheduler_ref):
    """
    Démarre scheduler.py en boucle infinie (exactement comme dans app.py).

    scheduler_ref = {"proc": process | None}
    """
    # Déjà en cours ?
    if scheduler_ref["proc"] and scheduler_ref["proc"].poll() is None:
        append_log(win, "[Scheduler] déjà en cours.")
        return

    cmd = [get_python_exe(), str(ROOT / "scheduler.py")]

    try:
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT)
        )

        scheduler_ref["proc"] = p
        append_log(win, "[Scheduler] démarré.")

        # Thread lecteur des logs
        def reader_thread(proc):
            try:
                for line in proc.stdout:
                    win.write_event_value("-SCHED-LOG-", line)
                proc.wait()
                win.write_event_value("-SCHED-DONE-", proc.returncode)
            except Exception as e:
                win.write_event_value("-SCHED-LOG-", f"[Scheduler][ERREUR thread] {e}\n")
                win.write_event_value("-SCHED-DONE-", -1)

        threading.Thread(target=reader_thread, args=(p,), daemon=True).start()

    except Exception as e:
        append_log(win, f"[Scheduler] erreur au démarrage : {e}")


# ==========================================================================
# 🔥 2) STOP SCHEDULER
# ==========================================================================
def stop_scheduler(win, scheduler_ref):
    p = scheduler_ref["proc"]

    if not p:
        append_log(win, "[Scheduler] Aucun scheduler actif.")
        return

    try:
        # Récupérer l’arbre des processus
        parent = psutil.Process(p.pid)
        children = parent.children(recursive=True)

        # Tuer tous les sous-processus (Appium, adb, runner…)
        for child in children:
            try:
                child.kill()
            except:
                pass

        # Tuer le scheduler lui-même
        parent.kill()

        append_log(win, "[Scheduler] Arrêt complet (processus + sous-processus).")

    except Exception as e:
        append_log(win, f"[Scheduler] Erreur lors de l'arrêt : {e}")

    scheduler_ref["proc"] = None


# ==========================================================================
# 🔥 3) REFRESH PLANNING (Onglet Programmation)
# ==========================================================================
def refresh_planning(win):
    """
    Recharge le tableau de programmation (-SCHED-TABLE-)
    en utilisant scheduler.build_planning().
    """

    data = build_planning()     # → Profil / System / Engine / Albums…
    win["-SCHED-TABLE-"].update(values=data)

    # Recalcul du total des Counts (colonne index 6 dans ton planning)
    total = 0
    for row in data:
        try:
            total += int(row[6])
        except:
            pass

    win["-SCHED-TOTAL-"].update(str(total))


# ==========================================================================
# 🔥 4) SYNCHRO Albums → Matrix (counts multi)
# ==========================================================================
def sync_album_to_matrix(album_name, albums_dict, matrix_rows):
    """
    Applique count_per_post de l'album aux lignes matrix qui l'utilisent.
    Logique 100% identique à app.py.
    """
    cfg = albums_dict.get(album_name)
    if not cfg:
        return

    # Seulement pour albums multi
    if cfg.get("kind") != "multi":
        return

    new_count = cfg.get("count_per_post")
    if not new_count:
        return

    changed = False
    for r in matrix_rows:
        # album multi standard
        if r.get("album2") == album_name:
            r["count"] = int(new_count)
            changed = True

        # anciens scénarios
        elif r.get("engine") == "multi" and r.get("album") == album_name:
            r["count"] = int(new_count)
            changed = True

    return changed


def sync_all_albums_to_matrix(win, albums_dict, matrix_rows):
    """
    Synchronise TOUS les albums multi vers la Matrix.
    Identique à app.py.
    """
    changed_any = False

    for name, cfg in albums_dict.items():
        if cfg.get("kind") == "multi":
            changed = sync_album_to_matrix(name, albums_dict, matrix_rows)
            if changed:
                changed_any = True

    # Sauvegarder si modifié
    if changed_any:
        save_json(MATRIX, {"rows": matrix_rows})
        append_log(win, "[Scheduler] Matrix synchronisée depuis Albums.")


# ==========================================================================
# 🔥 5) INJECTER HEURE LOGIQUE DANS STORYFX_TIME
# ==========================================================================
def apply_logical_time_env(win):
    """
    Récupère le logical_time (get_logical_minute())
    et applique STORYFX_TIME="MM:00"
    EXACTEMENT comme dans app.py avant le lancement du runner.
    """
    try:
        logical = get_logical_minute()
        os.environ["STORYFX_TIME"] = logical + ":00"
        append_log(win, f"[StoryFX] Heure logique appliquée : {logical}:00")
    except Exception as e:
        append_log(win, f"[StoryFX] Impossible d'appliquer l'heure logique : {e}")


# ==========================================================================
# 🔥 6) HANDLE UI EVENTS (LE PLUS IMPORTANT)
# ==========================================================================
def handle_scheduler_events(ev, vals, win, scheduler_ref, albums_dict, matrix_rows):
    """
    Point d’entrée unique appelé depuis app.py :

    handle_scheduler_events(
        ev,
        vals,
        win,
        {"proc": scheduler_proc},
        albums_dict,
        matrix_rows
    )

    Ici on récupère **TOUT** ce qui concerne la programmation :
    - Start / Stop scheduler
    - Logs
    - Refresh planning
    - Sync albums → matrix
    """

    # Rafraîchir
    if ev == "-SCHED-REFRESH-":
        refresh_planning(win)
        return True

    # Start (depuis 2 boutons)
    if ev in ("-SCHED-START-", "-SCHED-START-L-"):
        start_scheduler(win, scheduler_ref)
        return True

    # Stop (depuis 2 boutons)
    if ev in ("-SCHED-STOP-", "-SCHED-STOP-L-"):
        stop_scheduler(win, scheduler_ref)
        return True

    # Log scheduler
    if ev == "-SCHED-LOG-":
        line = vals.get("-SCHED-LOG-", "")
        if not line:
            return True

        clean = strip_ansi(line).rstrip()
        txt = clean.strip()
        if not txt:
            return True

        # 🔇 1) BRUIT À IGNORER COMPLETEMENT
        noisy_prefixes = (
            "[HTTP]",  # Appium HTTP proxy
            "[ADB]",  # bruit ADB
            "[AppiumDriver@",  # driver interne
            "[AndroidUiautomator2Driver@",  # driver interne
            "[Logcat]",  # logcat bruit
            "[SettingsApp]",  # settings internes
        )
        if txt.startswith(noisy_prefixes):
            return True

        # 🔊 2) LIGNES UTILES À GARDER
        # On garde :
        #   - tout ce qui contient [StoryFX]
        #   - tout ce qui commence par [Scheduler]
        #   - les messages Appium de haut niveau ([Appium] ... )
        keep = (
            ("[StoryFX]" in txt)
            or txt.startswith("[Scheduler]")
            or txt.startswith("[Appium]")
            or txt.startswith("Traceback")
            or txt.startswith("File ")
            or "WebDriverException" in txt
            or "uiautomator2" in txt.lower()
            or "instrumentation" in txt.lower()
            or "unknown server-side error" in txt.lower()
        )

        if keep:
            append_log(win, "[Scheduler] " + txt)
        return True


    # Fin du scheduler
    if ev == "-SCHED-DONE-":
        code = vals.get("-SCHED-DONE-")
        append_log(win, f"[Scheduler] terminé, code={code}")
        scheduler_ref["proc"] = None
        return True

    # Sync Albums → Matrix
    if ev == "-ALB_SYNC-":
        sync_all_albums_to_matrix(win, albums_dict, matrix_rows)
        return True

    return False   # → pas un event du scheduler
