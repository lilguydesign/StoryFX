# ui/ui_runner.py
# -*- coding: utf-8 -*-
"""
MODULE : Gestion complète du RUNNER (UI)

Ce module extrait TOUT ce qui concerne le lancement du runner
depuis app.py, y compris :

- Vérification Appium (auto-démarrage si off)
- Préparation du bon téléphone (adb connect device_id)
- Construction complète de la commande runner.py
- Gestion intro / multi / intro+multi
- Albums intro / albums multi
- Pays (page) + Page Facebook (page_name)
- Count automatique
- STORYFX_TIME (heure logique)
- Lancement du runner + thread de logs
- Gestion logs UI
- Arrêt du runner + kill apps
- Sauvegarde ui_state.json

Ce MODULE est 100 % propre et ne contient PLUS de duplication.
"""

import socket, subprocess
import threading
import os
import PySimpleGUI as sg
import time  # en haut du fichier

from ui.ui_paths_helpers import (
    ROOT,
    RUNNER,
    PROFILES,
    get_python_exe,
    append_log,
    adb_run,
    save_ui_state,
    strip_ansi,  # 👈 ajout
)

# 🔥 Fonction officielle (appelée dans TOUT StoryFX)
from ui.ui_devices import ensure_appium_running

from scheduler import get_logical_minute


# ==========================================================================
# 🔥 1) Connecter le BON téléphone avant le run
# ==========================================================================
def connect_profile_device(win, profile_cfg):
    """
    Reproduit exactement la logique de app.py :
        adb disconnect
        adb connect <device_id>
    """

    device_id = (profile_cfg.get("device_id") or "").strip()

    if not device_id:
        append_log(win, "[Devices] ATTENTION : aucun device_id défini pour ce profil.")
        return

    append_log(win, f"[Devices] Préparation du device {device_id}…")

    # 1) vider les connexions ADB
    adb_run("adb disconnect")

    # 2) reconnecter
    code, out = adb_run(f"adb connect {device_id}")
    msg = out.strip() or f"adb connect {device_id} (code={code})"
    append_log(win, msg)


# ==========================================================================
# 🔥 2) Construire la commande complete du runner
# ==========================================================================
def build_runner_cmd(vals, profile_name, profile_cfg, albums_dict):
    """
    Reproduit exactement la logique de construction de commande du runner :
        - engine intro / multi / intro+multi
        - selection des albums
        - count
        - platform / page / page_name / ig_variant
    """

    engine_ui = vals.get("-ENGINE-") or "intro"

    if engine_ui == "intro":
        engine = "intro"
    elif engine_ui == "multi":
        engine = "multi"
    else:
        engine = "intro_multi"

    album_intro = (vals.get("-ALBUM-") or "").strip()
    album_multi = (vals.get("-ALBUM2-") or "").strip()

    # Validation
    if engine == "intro" and not album_intro:
        sg.popup_error("Choisis un album (intro).")
        return None

    if engine == "multi" and not album_multi:
        sg.popup_error("Choisis un album (multi).")
        return None

    if engine == "intro_multi" and (not album_intro or not album_multi):
        sg.popup_error("Choisis un album intro ET un album multi.")
        return None

    # Count
    count_val = vals.get("-COUNT-", 11)
    try:
        count = str(int(count_val))
    except:
        count = "11"

    # Plateforme
    platform = vals.get("-PLATFORM_", vals.get("-PLATFORM-", "WhatsApp"))

    # Pays / Page
    page      = (vals.get("-PAGE-") or "").strip()       # Pays
    page_name = (vals.get("-PAGE_NAME-") or "").strip()  # Page Facebook

    # Commande finale
    cmd = [
        get_python_exe(), str(RUNNER),
        "--profiles", str(PROFILES),
        "--profile", profile_name,
        "--engine", engine,
        "--platform", platform,
    ]

    # Albums
    if engine == "intro":
        cmd += ["--album", album_intro]

    elif engine == "multi":
        cmd += ["--album", album_multi, "--count", count]

    elif engine == "intro_multi":
        cmd += ["--album", album_intro, "--album2", album_multi, "--count", count]

    # Pages
    if page:
        cmd += ["--page", page]
    if page_name:
        cmd += ["--page-name", page_name]


    return cmd


# ==========================================================================
# 🔥 3) Injecter l’heure logique
# ==========================================================================
def apply_logical_time(win):
    """
    Insère STORYFX_TIME dans les variables d’environnement
    pour que runner.py simule l'heure logique du scheduler.
    """

    try:
        logical = get_logical_minute()
        os.environ["STORYFX_TIME"] = logical + ":00"
        append_log(win, f"[StoryFX] Heure logique appliquée : {logical}:00")
    except Exception as e:
        append_log(win, f"[StoryFX] Impossible d’appliquer l’heure logique : {e}")


# ==========================================================================
# 🔥 4) Lancer runner.py + lire les logs sans BLOQUER l’UI
# ==========================================================================
def start_runner_process(win, cmd, runner_ref):
    """
    Démarre runner.py en tâche de fond,
    et lit les logs ligne par ligne dans un thread.
    """

    append_log(win, " ".join(cmd))

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

        runner_ref["proc"] = p

        def reader_thread(proc):
            try:
                for line in proc.stdout:
                    win.write_event_value("-RUNNER-LOG-", line)
                proc.wait()
                win.write_event_value("-RUNNER-DONE-", proc.returncode)
            except Exception as e:
                win.write_event_value("-RUNNER-LOG-", f"[UI][ERREUR thread] {e}\n")
                win.write_event_value("-RUNNER-DONE-", -1)

        threading.Thread(target=reader_thread, args=(p,), daemon=True).start()

    except Exception as e:
        append_log(win, f"[UI][ERREUR démarrage runner] {e}")


# ==========================================================================
# 🔥 5) Stopper runner + kill apps mobiles
# ==========================================================================
def stop_runner(win, runner_ref):
    """
    Arrête proprement le runner + reset de l'écran côté téléphone.
    """

    p = runner_ref["proc"]

    if p and p.poll() is None:
        append_log(win, "[UI] arrêt du runner en cours...")
        try:
            p.terminate()
            p.wait(timeout=3)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

        append_log(win, "[UI] runner stoppé.")
    else:
        append_log(win, "[UI] aucun runner actif à stopper.")

    # On oublie l'ancien process dans le ref
    runner_ref["proc"] = None

    # 🔥 Reset complet du téléphone (force-stop + BACK + HOME)
    append_log(win, "[UI] arrêt des applications mobiles…")
    reset_phone_to_home(win)


# ==========================================================================
# 🔥 6) Sauvegarde de l'état UI
# ==========================================================================
def save_ui_after_run(vals, ui_state_path):
    """
    Sauvegarde l’état courant UI pour restauration au prochain démarrage.
    """

    engine_ui = vals.get("-ENGINE-") or "intro"

    ui_state = {
        "profile":      vals.get("-PROFILE-"),
        "engine":       engine_ui,
        "album_intro":  vals.get("-ALBUM-", ""),
        "album_multi":  vals.get("-ALBUM2-", ""),
        "platform":     vals.get("-PLATFORM-", "WhatsApp"),
        "page":         vals.get("-PAGE-", ""),
        "page_name":    vals.get("-PAGE_NAME-", ""),
    }

    save_ui_state(ui_state)


# ==========================================================================
# 🔥 7) Gestion des événements Runner depuis l’UI
# ==========================================================================
def handle_runner_events(ev, vals, win, runner_ref, profiles, albums_dict, ui_state_path):
    """
    Gère :
        - démarrage du RUNNER
        - arrêt
        - logs
        - fin du runner
    """

    # STOP RUNNER
    if ev == "-RUN_STOP-":
        stop_runner(win, runner_ref)
        return True

    # Logs
    if ev == "-RUNNER-LOG-":
        line = vals.get("-RUNNER-LOG-", "")
        if not line:
            return True

        clean = strip_ansi(line).rstrip()
        txt = clean.strip()
        if not txt:
            return True

        # ✅ On garde :
        # - logs StoryFX
        # - logs [runner]
        # - stacktraces Python (Traceback + File + exceptions)
        keep = (
            "[StoryFX]" in txt
            or txt.startswith("[runner]")
            or txt.startswith("Traceback")
            or txt.startswith("  File ")
            or "WebDriverException" in txt
            or "ConnectionRefusedError" in txt
            or "ECONNREFUSED" in txt
            or "uiautomator2" in txt.lower()
            or "instrumentation" in txt.lower()
        )

        if keep:
            append_log(win, txt)

        return True

    if ev == "-RUNNER-DONE-":
        code = vals.get("-RUNNER-DONE-")
        append_log(win, f"[UI] terminé, code={code}")
        runner_ref["proc"] = None
        return True

    # START RUN
    if ev == "-RUN-":

        # 🔥 0) Nettoyer l'écran du téléphone AVANT TOUT
        reset_phone_to_home(win)

        # 🔥 Indispensable : démarrer Appium s'il n'est pas actif
        ensure_appium_running()

        profile_name = vals.get("-PROFILE-")
        if not profile_name:
            sg.popup_error("Choisis un profil.")
            return True

        profile_cfg = profiles.get(profile_name, {})

        if not profile_cfg.get("enabled", True):
            sg.popup_error("Ce device est désactivé dans les profils.")
            return True

        # Connecter le bon téléphone
        connect_profile_device(win, profile_cfg)

        # Construire la commande runner.py
        cmd = build_runner_cmd(vals, profile_name, profile_cfg, albums_dict)
        if not cmd:
            return True

        # Injecter l’heure logique
        apply_logical_time(win)

        # Afficher commande
        append_log(win, " ".join(cmd))

        # Sauvegarde UI
        save_ui_after_run(vals, ui_state_path)

        # Lancer runner + logs en temps réel
        start_runner_process(win, cmd, runner_ref)

        return True

    return False  # cet event ne concerne pas le runner

UNWANTED_PACKAGES = [
    # Galerie + réseaux
    "com.sec.android.gallery3d",
    "com.facebook.katana",
    "com.facebook.orca",
    "com.facebook.lite",
    "com.instagram.android",
    "com.zhiliaoapp.musically",
    # Applis de rappels / horloge / calendrier
    "com.sec.android.app.clockpackage",   # Horloge Samsung
    "com.google.android.deskclock",       # Horloge Google
    "com.google.android.calendar",
    "com.samsung.android.calendar",
]

def reset_phone_to_home(win):
    """
    1) Force-stop des applis connues (Galerie, FB, IG, TikTok, Clock, Calendar…)
    2) Fermeture des popups USSD/MMI avec plusieurs BACK
    3) Retour à la page d'accueil (HOME)
    """
    append_log(win, "[UI] Reset de l'écran Android avant le run…")

    # 1) Fermer les apps connues
    for pkg in UNWANTED_PACKAGES:
        try:
            adb_run(f"adb shell am force-stop {pkg}")
        except Exception as e:
            append_log(win, f"[UI] Impossible de fermer {pkg} : {e}")

    # 2) Fermer les popups USSD/MMI (Connection problem / invalid MMI)
    # BACK plusieurs fois pour fermer les boîtes de dialogue
    for _ in range(4):
        adb_run("adb shell input keyevent 4")  # KEYCODE_BACK
        time.sleep(0.2)

    # 3) Retour à la Home
    adb_run("adb shell input keyevent 3")      # KEYCODE_HOME
    time.sleep(0.5)