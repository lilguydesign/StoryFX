# ui/ui_devices.py
# -*- coding: utf-8 -*-
"""
Module ADB complet pour StoryFX (version PRO refondue).

Fonctionnalités :
    ✔ auto_connect_all_devices (USB → Wi-Fi)
    ✔ connect_all_devices (connexion PRO)
    ✔ disconnect_all_devices (reset serveur ADB, vue PRO)
    ✔ list_devices_pro (vue PRO avec 🟢 / 🔴 / ⚪ + fusion des profils)
    ✔ copier serial(s) (via LAST_USB_SERIALS + get_last_usb_serials)
    ✔ propagation automatique IP/port/device_id entre profils liés
    ✔ mapping centralisé des devices (Wi-Fi / USB / désactivés)
    ✔ logs propres formatés, sans doublons

CONVENTIONS :
    - Un "périphérique réel" est identifié par son device_id (IP:PORT).
    - Plusieurs profils peuvent partager le même device_id : ils sont fusionnés
      dans l'affichage (ex: S23 (WA, IG, FB_CM, FB_CI, TikTok) (192.168.1.123:5555)).
    - Les serials USB sont affichés UNIQUEMENT dans la section USB.
"""
import shutil
from concurrent.futures import ThreadPoolExecutor
import requests

import os
import time
import socket
import subprocess

APPIUM_HOST = "127.0.0.1"
APPIUM_PORT = 4723
ADB_STORYFX = r"C:\Tools\ADB_StoryFX\adb.exe"   # ton adb séparé
ADB_PORT_STORYFX = "5038"                      # IMPORTANT: ne touche pas 5037

from typing import Dict, Any, List, Tuple
import re
from subprocess import Popen, PIPE
import subprocess, time, socket, os, shutil, requests

from ui.ui_paths_helpers import (
    adb_run,
    load_profiles_dict,
    save_json,
    PROFILES,
)

# Mémorise les derniers serials USB détectés (pour le bouton "Copier serial(s)")
LAST_USB_SERIALS: List[str] = []

# ==========================================================================
# 🔥 Ensure Appium Running (Auto-start si Appium n'est pas lancé)
# ==========================================================================

def scan_adb_devices_fast() -> tuple[set, set, str, str]:
    """
    Scan ultra rapide (preuve 5037 + 5038):
    - USB via 5037 (adb_run_sdk)
    - Wi-Fi via 5038 (adb_run)
    - exécute 5037 et 5038 en parallèle
    Retourne:
      usb_serials_device, wifi_ids_device, out_5037, out_5038
    """

    def _usb_5037():
        _, out = adb_run_sdk("adb devices")
        usb = set()
        for serial, status in _parse_adb_devices(out):
            if _is_emulator_serial(serial):
                continue
            if ":" in serial:
                continue
            if status == "device":
                usb.add(serial)
        return usb, (out or "")

    def _wifi_5038():
        _, out = adb_run("adb devices")  # 5038
        wifi = set()
        for serial, status in _parse_adb_devices(out):
            if _is_emulator_serial(serial):
                continue
            if ":" in serial and status == "device":
                wifi.add(serial)
        return wifi, (out or "")

    with ThreadPoolExecutor(max_workers=2) as ex:
        f_usb = ex.submit(_usb_5037)
        f_wifi = ex.submit(_wifi_5038)
        usb, out_5037 = f_usb.result()
        wifi, out_5038 = f_wifi.result()

    # fallback wifi lecture 5037 si 5038 vide
    if not wifi:
        for serial, status in _parse_adb_devices(out_5037):
            if _is_emulator_serial(serial):
                continue
            if ":" in serial and status == "device":
                wifi.add(serial)

    return usb, wifi, out_5037, out_5038

# ============================================================
# 1) ADB ANDROID STUDIO → PORT 5037
# ============================================================
def start_android_studio_adb():
    """
    Démarre ADB Android Studio sur le port 5037.
    Garantit que l’ADB officiel ne vole pas le port 5038.
    """

    SDK_ADB = r"C:\Users\lilgu\AppData\Local\Android\Sdk\platform-tools\adb.exe"

    # kill-server NE dépend PAS de ANDROID_ADB_SERVER_PORT
    subprocess.run([SDK_ADB, "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # start-server démarre TOUJOURS sur 5037
    subprocess.run([SDK_ADB, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ============================================================
# 2) ADB STORYFX → PORT 5038
# ============================================================
# def start_storyfx_adb():
#     """
#     Lance le serveur ADB StoryFX (port 5038).
#     Utilisé pour gérer les téléphones en WiFi + Appium.
#     """
#
#     # FORCER UNIQUEMENT CE PROCESSUS À UTILISER 5038
#     os.environ["ANDROID_ADB_SERVER_PORT"] = "5038"
#
#     STORYFX_ADB = r"C:\Tools\ADB_StoryFX\adb.exe"
#
#     # Redémarrage complet
#     subprocess.run([STORYFX_ADB, "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#     subprocess.run([STORYFX_ADB, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#

from pathlib import Path

def _parse_adb_devices(out: str):
    """Parse adb devices → [(serial, status), ...] sans l'entête."""
    items = []
    for line in (out or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            items.append((parts[0].strip(), parts[1].strip()))
    return items

def _is_emulator_serial(serial: str) -> bool:
    s = (serial or "").lower()
    return ("emulator" in s) or ("5554" in s)

def launch_appium_from_bat(win=None) -> bool:
    import subprocess, time, socket

    def _log(msg: str):
        if win:
            win.write_event_value("-RUNNER-LOG-", msg)
        else:
            print(msg, flush=True)

    bat = r"C:\Tools\Lancer_Appium_StoryFX.bat"  # adapte si besoin

    try:
        p = subprocess.Popen(
            ["cmd", "/c", bat],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception as e:
        _log(f"[Appium] BAT launch error: {e!r}")
        return False

    # laisse le temps au .bat de lancer appium
    time.sleep(1.0)

    # check port
    try:
        with socket.create_connection((APPIUM_HOST, APPIUM_PORT), timeout=0.5):
            _log("[Appium] BAT: port OK ✅")
            return True
    except Exception:
        # lire quelques lignes du .bat
        out = ""
        try:
            if p.stdout:
                for _ in range(40):
                    line = p.stdout.readline()
                    if not line:
                        break
                    out += line
        except Exception:
            pass

        _log(f"[Appium] BAT: port NOT open ❌\n--- bat output ---\n{out}")
        return False



# ============================================================
# 3) ASSURER APPIUM → PORT 4723 + ADB PORT 5038
# ============================================================
def find_appium_cmd() -> str | None:
    import os, shutil, subprocess

    # 1) si déjà dans PATH
    p = shutil.which("appium.cmd") or shutil.which("appium")
    if p:
        return p

    # 2) fallback direct sur le chemin connu (ton where appium)
    hard = r"C:\Users\lilgu\AppData\Roaming\npm\appium.cmd"
    if os.path.exists(hard):
        return hard

    # 3) npm prefix -g => chemin global npm
    try:
        npm = shutil.which("npm") or "npm"
        prefix = subprocess.check_output([npm, "prefix", "-g"], text=True).strip()
        candidate = os.path.join(prefix, "node_modules", ".bin", "appium.cmd")
        if os.path.exists(candidate):
            return candidate
    except Exception:
        pass

    return None

def ensure_appium_running(win=None) -> bool:
    import os, time, socket, shutil, subprocess, requests

    def _log(msg: str):
        if win:
            win.write_event_value("-RUNNER-LOG-", msg)
        else:
            print(msg, flush=True)

    t0 = time.time()
    _log("[Appium] ensure_appium_running() start")

    # 0) anti-freeze global (max 30s ici)
    MAX_TOTAL = 30

    def _time_left():
        return MAX_TOTAL - (time.time() - t0)

    # 1) Appium déjà UP ?
    _log(f"[Appium] check existing server {APPIUM_HOST}:{APPIUM_PORT} ...")
    try:
        with socket.create_connection((APPIUM_HOST, APPIUM_PORT), timeout=0.5):
            try:
                r = requests.get(f"http://{APPIUM_HOST}:{APPIUM_PORT}/wd/hub/status", timeout=0.8)
                if r.status_code == 200:
                    _log("[Appium] already UP ✅")
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # 2) ADB 5038 + PATH process (StoryFX)
    _log(f"[Appium] adb start-server on port {ADB_PORT_STORYFX} ...")

    env = os.environ.copy()
    env["ANDROID_ADB_SERVER_PORT"] = str(ADB_PORT_STORYFX)

    # PATCH PATH (IMPORTANT: ordre = nodejs -> npm -> adb -> PATH existant)
    node_path = r"C:\Program Files\nodejs"
    npm_bin_path = r"C:\Users\lilgu\AppData\Roaming\npm"
    adb_path = r"C:\Tools\ADB_StoryFX"

    env["PATH"] = ";".join([
        node_path,
        npm_bin_path,
        adb_path,
        env.get("PATH", ""),
    ])

    _log("[Appium] PATH patched (nodejs + npm + adb)")

    # start adb 5038
    try:
        subprocess.run(
            [ADB_STORYFX, "start-server"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        _log("[Appium] adb start-server OK")
    except Exception as e:
        _log(f"[Appium] WARN adb start-server failed: {e!r}")

    # 3) Start Appium
    appium_bin = find_appium_cmd() or "appium"
    _log(f"[Appium] resolved appium_bin = {appium_bin!r}")

    # --- log file Appium (indispensable pour diagnostiquer quand stdout ne sort rien)
    log_dir = r"C:\Temp"
    os.makedirs(log_dir, exist_ok=True)
    appium_log = os.path.join(log_dir, "storyfx_appium.log")
    # 🔥 IMPORTANT : supprimer l'ancien log Appium (évite de lire une vieille erreur)
    try:
        if os.path.exists(appium_log):
            os.remove(appium_log)
    except Exception:
        pass

    args = [
        "--allow-cors",
        "--relaxed-security",
        "--base-path", "/wd/hub",
        "--address", APPIUM_HOST,
        "--port", str(APPIUM_PORT),
        # "--adb-port", str(ADB_PORT_STORYFX),

        # 🔥 DEBUG LOGS (sinon tu ne vois rien)
        "--log", appium_log,
        "--log-level", "debug",
    ]
    _log(f"[Appium] log file = {appium_log}")

    proc = None
    _log(f"[Appium] launching: {appium_bin} {' '.join(args)}")

    try:
        if str(appium_bin).lower().endswith(".cmd"):
            proc = subprocess.Popen(
                ["cmd", "/c", appium_bin, *args],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                stdin=subprocess.DEVNULL,
            )
        else:
            proc = subprocess.Popen(
                [appium_bin, *args],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                stdin=subprocess.DEVNULL,
            )
    except (FileNotFoundError, OSError) as e:
        _log(f"[Appium] launch error: {e!r}. fallback .bat ...")
        if launch_appium_from_bat(win=win):
            _log("[Appium] launched from .bat, waiting port...")
            proc = None  # lancé par bat, pas de proc à gérer ici
        else:
            raise RuntimeError("[Appium] introuvable (PATH) et .bat fallback a échoué.")

    # 3.1) Pump logs Appium en live (si proc géré par Python)
    import threading

    def _pump_appium_logs(p):
        try:
            if not p or not p.stdout:
                return
            for line in p.stdout:
                line = (line or "").rstrip()
                if line:
                    _log(f"[Appium][OUT] {line}")
        except Exception as e:
            _log(f"[Appium][OUT] (log pump error: {e!r})")

    if proc and proc.stdout:
        threading.Thread(target=_pump_appium_logs, args=(proc,), daemon=True).start()

    # 3.2) Lire rapidement le fichier log Appium (même si stdout est vide)
    time.sleep(0.8)
    try:
        if os.path.exists(appium_log):
            with open(appium_log, "r", encoding="utf-8", errors="replace") as f:
                tail = f.read()[-2000:]  # derniers caractères
            if tail.strip():
                _log("[Appium][LOGTAIL]\n" + tail.strip())
        else:
            _log(f"[Appium] log file not found yet: {appium_log}")
    except Exception as e:
        _log(f"[Appium] cannot read log file: {e!r}")

    # 3bis) si le process meurt direct, on récupère le log tout de suite
    if proc:
        time.sleep(0.6)
        rc = proc.poll()
        if rc is not None:
            out = ""
            try:
                out = proc.stdout.read() if proc.stdout else ""
            except Exception:
                pass
            raise RuntimeError(f"[Appium] process exited immediately rc={rc}\n--- output ---\n{out}")

    # 4) Attendre port (avec logs + détection crash + fallback .bat)
    _log("[Appium] waiting for port to listen ...")
    port_ok = False

    # 4a) attente port (30s)
    for i in range(120):  # 120 * 0.25s = 30s
        if proc:
            rc = proc.poll()
            if rc is not None:
                raise RuntimeError(
                    f"[Appium] Appium s'est fermé pendant l'attente (rc={rc}). "
                    f"Regarde les logs [Appium][OUT] juste au-dessus."
                )
        try:
            with socket.create_connection((APPIUM_HOST, APPIUM_PORT), timeout=0.5):
                port_ok = True
                break
        except Exception:
            _log(f"[Appium] attente port {APPIUM_PORT}... ({i + 1}/120)")
            time.sleep(0.25)

    # 4b) fallback .bat si port toujours pas ouvert
    if not port_ok:
        _log("[Appium] port not open. trying fallback .bat ...")
        if launch_appium_from_bat(win=win):  # <-- passe win si ta fonction l'accepte
            for j in range(120):  # 30s de plus
                try:
                    with socket.create_connection((APPIUM_HOST, APPIUM_PORT), timeout=0.5):
                        port_ok = True
                        break
                except Exception:
                    _log(f"[Appium] (bat) attente port {APPIUM_PORT}... ({j + 1}/120)")
                    time.sleep(0.25)

    # 4c) dernier recours : raise avec output
    if not port_ok:
        out = ""
        if proc:
            try:
                out, _ = proc.communicate(timeout=1.0)
            except Exception:
                out = ""
        raise RuntimeError(
            f"[Appium] Port {APPIUM_PORT} ne s'est jamais ouvert.\n"
            f"--- output ---\n{out}"
        )

    # 5) Attendre /status
    _log("[Appium] port OK. waiting /status ...")
    for _ in range(20):
        try:
            r = requests.get(f"http://{APPIUM_HOST}:{APPIUM_PORT}/wd/hub/status", timeout=0.8)
            if r.status_code == 200:
                _log("[Appium] status OK ✅")
                return True
        except Exception:
            _log("[Appium] attente /wd/hub/status ...")
            time.sleep(0.25)

    out = ""
    if proc:
        try:
            out, _ = proc.communicate(timeout=1.0)
        except Exception:
            out = "[Appium] (no logs / still running)"

    raise RuntimeError(f"[Appium] /status not ready.\n--- output ---\n{out}")

# ==========================================================================
# 🔥 0. Helpers génériques : mapping, labels, adb devices
# ==========================================================================

def build_devices_mapping(profiles: dict) -> Tuple[dict, dict, dict, int]:
    """
    Construit TOUT le mapping des appareils réels à partir de profiles.json.

    Retourne :
        wifi_map      : dict[device_id] -> [profil1, profil2, ...] (uniquement enabled)
        usb_map       : dict[serial]    -> [profil1, profil2, ...] (uniquement enabled)
        disabled_map  : dict[device_id] -> [profils désactivés]
        unique_count  : nombre total de téléphones réels (len(wifi_map))

    NOTE :
        - On considère que l'identifiant "unique" d'un téléphone est son device_id (IP:PORT).
        - Les serials USB servent uniquement à savoir quel téléphone est branché en USB.
    """
    wifi_map: Dict[str, List[str]] = {}
    usb_map: Dict[str, List[str]] = {}
    disabled_map: Dict[str, List[str]] = {}

    for name, cfg in profiles.items():
        dev_id = (cfg.get("device_id") or "").strip()
        serial = (cfg.get("adb_serial") or "").strip()
        enabled = cfg.get("enabled", True)

        if not enabled:
            if dev_id:
                disabled_map.setdefault(dev_id, []).append(name)
            else:
                # périphérique désactivé sans device_id (rare)
                disabled_map.setdefault("", []).append(name)
            continue

        if dev_id:
            wifi_map.setdefault(dev_id, []).append(name)

        if serial:
            usb_map.setdefault(serial, []).append(name)

    unique_count = len(wifi_map)
    return wifi_map, usb_map, disabled_map, unique_count


def fusion_label(profiles_list: List[str]) -> str:
    """
    Crée un label fusionné PRO à partir d'une liste de profils.

    Exemples :
        ["S23_FB_CM", "S23_IG", "S23_WA"]
            → "S23 (FB_CM, IG, WA)"

        ["A16"]
            → "A16"
    """
    if not profiles_list:
        return ""

    # Préfixe principal (avant le premier "_")
    prefixes = [p.split("_")[0] for p in profiles_list]
    main_prefix = prefixes[0]

    # Noms courts (on enlève "S23_", "G2_", etc.)
    short_names = [p.replace(main_prefix + "_", "") for p in profiles_list]

    if len(profiles_list) == 1:
        # Un seul profil → on garde le nom brut
        return profiles_list[0]

    joined = ", ".join(short_names)
    return f"{main_prefix} ({joined})"

def _get_usb_serials_and_port() -> tuple[list[str], int, str, str]:
    """
    Cherche les serials USB sur 5038 d'abord, puis 5037.
    Retourne : (serials, port_used, raw5038, raw5037)
    """
    # 5038
    _, out_38 = adb_run("adb devices")
    usb_38 = [s for s, st in _parse_adb_devices(out_38)
              if st == "device" and ":" not in s and not _is_emulator_serial(s)]

    # 5037 (même adb.exe mais port serveur 5037)
    _, out_37 = adb_run("adb devices", port=5037)
    usb_37 = [s for s, st in _parse_adb_devices(out_37)
              if st == "device" and ":" not in s and not _is_emulator_serial(s)]

    if usb_38:
        return sorted(usb_38), 5038, (out_38 or ""), (out_37 or "")
    return sorted(usb_37), 5037, (out_38 or ""), (out_37 or "")

def adb_run_sdk(cmd: str):
    """
    Exécute une commande ADB via le binaire Android Studio (serveur 5037).
    Utilisé pour tout ce qui touche l'USB (devices, ip route, tcpip).
    """
    SDK_ADB = r"C:\Users\lilgu\AppData\Local\Android\Sdk\platform-tools\adb.exe"
    env = os.environ.copy()
    # on s'assure de parler au serveur par défaut (5037)
    env.pop("ANDROID_ADB_SERVER_PORT", None)

    cmd = cmd.strip()
    if cmd.startswith("adb "):
        cmd = f"\"{SDK_ADB}\" {cmd[4:]}"
    elif cmd == "adb":
        cmd = f"\"{SDK_ADB}\""

    try:
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

def build_device_name_map(profiles: dict) -> dict:
    """
    Mapping brut : serial_ou_device_id -> nom lisible (label).

    Utilisé surtout pour :
        - auto_connect_all_devices (affichage adb devices brut)
        - fallback pour les devices non fusionnés
    """
    name_map = {}
    for prof_name, cfg in profiles.items():
        label = cfg.get("label", prof_name)
        serial = (cfg.get("adb_serial") or "").strip()
        device_id = (cfg.get("device_id") or "").strip()

        if serial:
            name_map[serial] = label
        if device_id:
            name_map[device_id] = label
    return name_map


def _extract_ip_from_ip_route(text: str) -> str | None:
    """Analyse 'adb shell ip route' et récupère l'IP Wi-Fi."""
    m = re.search(r"\bsrc\s+(\d+\.\d+\.\d+\.\d+)", text)
    if m:
        return m.group(1)

    # fallback générique
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)", text)
    if m:
        return m.group(1)

    return None


def _build_adb_index(profiles: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Construit serial → liste des profils utilisant ce serial USB."""
    idx: Dict[str, List[str]] = {}
    for name, cfg in profiles.items():
        serial = (cfg.get("adb_serial") or "").strip()
        if serial:
            idx.setdefault(serial, []).append(name)
    return idx


def get_last_usb_serials() -> List[str]:
    """Retourne la dernière liste de serials USB détectés (pour le bouton Copier serial(s))."""
    return LAST_USB_SERIALS


def scan_adb_devices(wait_seconds: float = 3.0, poll_interval: float = 0.4) -> Tuple[set, set, str]:
    """
    Version PRO (stable + multi-ports) :
    - USB: scan/poll sur 5037 (adb_run_sdk) + capture unauthorized/offline
    - Wi-Fi: priorité 5038 (adb_run)
      fallback lecture 5037 si 5038 ne voit aucun ip:port device
    - ignore emulator/5554
    - retourne:
        usb_serials_device : serials USB OK (status=device)
        wifi_ids_device    : ip:port OK (status=device)
        raw_output         : logs combinés (avec statuts)
    """

    # Assurer ADB 5037 vivant
    try:
        start_android_studio_adb()
    except Exception:
        pass

    usb_serials_device = set()
    wifi_ids_device = set()

    usb_other_status: list[tuple[str, str]] = []
    wifi_other_status: list[tuple[str, str]] = []

    out_usb_final = ""
    out_wifi_5038 = ""
    out_wifi_5037 = ""

    # -------------------------
    # 1) Poll USB (5037)
    # -------------------------
    t0 = time.time()
    while time.time() - t0 < wait_seconds:
        _, out_usb = adb_run_sdk("adb devices")
        out_usb_final = out_usb or ""

        usb_serials_device.clear()
        usb_other_status.clear()

        for serial, status in _parse_adb_devices(out_usb_final):
            if _is_emulator_serial(serial):
                continue
            # USB => pas de ":" (sinon c'est ip:port)
            if ":" in serial:
                continue

            if status == "device":
                usb_serials_device.add(serial)
            else:
                usb_other_status.append((serial, status))

        # stop tôt si on a au moins 1 device USB prêt
        if usb_serials_device:
            break

        time.sleep(poll_interval)

    # -------------------------
    # 2) Wi-Fi priorité 5038 (StoryFX)
    # -------------------------
    _, out_wifi_5038 = adb_run("adb devices")  # 5038 par défaut dans ton app
    out_wifi_5038 = out_wifi_5038 or ""

    wifi_ids_device.clear()
    wifi_other_status.clear()

    for serial, status in _parse_adb_devices(out_wifi_5038):
        if _is_emulator_serial(serial):
            continue
        if ":" not in serial:
            continue

        if status == "device":
            wifi_ids_device.add(serial)
        else:
            wifi_other_status.append((serial, status))

    # -------------------------
    # 3) Fallback lecture Wi-Fi sur 5037 si 5038 ne voit rien
    # -------------------------
    if not wifi_ids_device:
        _, out_wifi_5037 = adb_run_sdk("adb devices")
        out_wifi_5037 = out_wifi_5037 or ""

        for serial, status in _parse_adb_devices(out_wifi_5037):
            if _is_emulator_serial(serial):
                continue
            if ":" not in serial:
                continue

            if status == "device":
                wifi_ids_device.add(serial)
            else:
                wifi_other_status.append((serial, status))

    # -------------------------
    # 4) Logs propres
    # -------------------------
    raw: list[str] = []
    raw.append("=== ADB 5037 (USB / émulateurs) ===")
    raw.append(out_usb_final.strip() or "(vide)")

    if usb_other_status:
        raw.append("\n[USB] Détectés mais NON prêts :")
        for s, st in usb_other_status:
            if st == "unauthorized":
                raw.append(f"  - {s} → unauthorized (déverrouille + accepte 'Allow USB debugging')")
            elif st == "offline":
                raw.append(f"  - {s} → offline (rebranche / change câble / attends 2s)")
            else:
                raw.append(f"  - {s} → {st}")

    raw.append("\n=== ADB 5038 (StoryFX Wi-Fi) ===")
    raw.append(out_wifi_5038.strip() or "(vide)")

    if out_wifi_5037:
        raw.append("\n=== ADB 5037 (fallback Wi-Fi) ===")
        raw.append(out_wifi_5037.strip() or "(vide)")

    if wifi_other_status:
        raw.append("\n[Wi-Fi] Détectés mais NON prêts :")
        for s, st in wifi_other_status:
            raw.append(f"  - {s} → {st}")

    return usb_serials_device, wifi_ids_device, "\n".join(raw)

# ==========================================================================
# 🔥 1. Déconnexion totale + vue PRO
# ==========================================================================

def disconnect_all_devices() -> str:
    """
    Reset ADB 5038 propre + vue PRO.
    """
    profiles = load_profiles_dict()
    wifi_map, usb_map, disabled_map, unique_count = build_devices_mapping(profiles)

    logs: List[str] = []
    logs.append("=== Reset ADB (Mode PRO) : déconnexion de tous les appareils ===\n")

    adb_run("adb disconnect")
    adb_run("adb kill-server")
    _, out = adb_run("adb start-server")
    logs.append((out or "").strip())

    usb_connected, wifi_connected, _ = scan_adb_devices(wait_seconds=1.5, poll_interval=0.3)

    logs.append("\n🟢 CONNECTÉS (USB) :")
    found_usb = False
    for serial, profils in usb_map.items():
        if serial in usb_connected:
            logs.append(f"   🟢 {fusion_label(profils)} ({serial})")
            found_usb = True
    for serial in usb_connected:
        if serial not in usb_map:
            logs.append(f"   🟢 {serial} (nouveau périphérique USB)")
            found_usb = True
    if not found_usb:
        logs.append("   Aucun device USB connecté.")

    logs.append("\n🟢 CONNECTÉS (Wi-Fi) :")
    found_wifi = False
    for dev_id, profils in wifi_map.items():
        if dev_id in wifi_connected:
            logs.append(f"   🟢 {fusion_label(profils)} ({dev_id})")
            found_wifi = True
    if not found_wifi:
        logs.append("   Aucun device Wi-Fi connecté.")

    logs.append("\n🔴 ABSENTS (Wi-Fi) :")
    abs_found = False
    for dev_id, profils in wifi_map.items():
        if dev_id not in wifi_connected:
            logs.append(f"   🔴 {fusion_label(profils)} ({dev_id}) → Hors ligne")
            abs_found = True
    if not abs_found:
        logs.append("   Aucun device absent.")

    logs.append("\n⚪ DÉSACTIVÉS :")
    if disabled_map:
        for dev_id, profils in disabled_map.items():
            dev_label = dev_id or "device_id inconnu"
            logs.append(f"   ⚪ {fusion_label(profils)} ({dev_label}) → Désactivé")
    else:
        logs.append("   Aucun device désactivé.")

    # comptage “actif”
    connected_devices_ids = set()
    for dev_id in wifi_map.keys():
        if dev_id in wifi_connected:
            connected_devices_ids.add(dev_id)
            continue
        for prof_name in wifi_map[dev_id]:
            serial = (profiles.get(prof_name, {}).get("adb_serial") or "").strip()
            if serial and serial in usb_connected:
                connected_devices_ids.add(dev_id)
                break

    logs.append(f"\n=== Résultat : {len(connected_devices_ids)} / {unique_count} périphériques actifs ===")
    return "\n".join(logs)

# ==========================================================================
# 🔥 2. Auto-connexion USB → Wi-Fi complète
# ==========================================================================

def auto_connect_all_devices(profiles: Dict[str, Dict[str, Any]]) -> str:
    """
    Auto-connexion USB → Wi-Fi (version PRO multi-ports) :

    Objectif :
    - détecter l’USB même si le téléphone apparaît sur 5038 (ADB StoryFX) OU 5037 (ADB Android Studio)
    - exécuter ip route + tcpip sur LE BON port (celui qui voit le serial USB)
    - connecter ensuite en Wi-Fi sur 5038
    - mettre à jour profiles.json + propagation des profils liés

    Notes :
    - ADB Wi-Fi (ip:port) doit être connecté sur 5038 (adb_run par défaut)
    - On ignore emulator / 5554
    """
    global LAST_USB_SERIALS

    logs: List[str] = []
    logs.append("=== Auto-connexion ADB (USB → Wi-Fi) ===")

    # ------------------------------------------------------------------
    # 0) Reload profils (source de vérité)
    # ------------------------------------------------------------------
    profiles = load_profiles_dict()

    # ------------------------------------------------------------------
    # 1) Détection USB sur 5038 d'abord, sinon fallback 5037
    # ------------------------------------------------------------------
    def _usb_serials_from_output(out: str) -> list[str]:
        serials = []
        for s, st in _parse_adb_devices(out or ""):
            if st != "device":
                continue
            if _is_emulator_serial(s):
                continue
            if ":" in s:  # ip:port => pas USB
                continue
            serials.append(s)
        return serials

    # Lire USB via adb_run (5038)
    _, out_38 = adb_run("adb devices")                 # 5038 (StoryFX)
    usb_38 = _usb_serials_from_output(out_38)

    # Lire USB via adb_run(port=5037)
    _, out_37 = adb_run("adb devices", port=5037)      # 5037 (fallback)
    usb_37 = _usb_serials_from_output(out_37)

    # Choisir le port USB à utiliser (priorité 5038 car ton cas réel)
    if usb_38:
        usb_port = 5038
        serials_usb = sorted(usb_38)
    else:
        usb_port = 5037
        serials_usb = sorted(usb_37)

    LAST_USB_SERIALS = serials_usb[:]

    logs.append("\n=== USB detection (5038 + 5037) ===")
    logs.append("[DEBUG] ADB 5038 raw (USB check):")
    logs.append((out_38 or "").strip() or "(vide)")
    logs.append("\n[DEBUG] ADB 5037 raw (USB check):")
    logs.append((out_37 or "").strip() or "(vide)")
    logs.append(f"\n✅ USB port utilisé = {usb_port}")

    if not serials_usb:
        logs.append("\n❌ Aucun appareil USB détecté (ni sur 5038 ni sur 5037).")
        logs.append("➡️ Vérifie : câble / port USB / téléphone déverrouillé / popup 'Allow USB debugging'.")
        return "\n".join(logs)

    # ------------------------------------------------------------------
    # 2) Index serial -> profils liés
    # ------------------------------------------------------------------
    adb_index = _build_adb_index(profiles)
    profiles_changed = False

    # ------------------------------------------------------------------
    # 3) Pour chaque serial USB : ip route + tcpip (sur usb_port), puis connect (5038)
    # ------------------------------------------------------------------
    for serial in serials_usb:
        logs.append(f"\n--- USB: {serial} (via port {usb_port}) ---")

        prof_names = adb_index.get(serial) or []
        if not prof_names:
            logs.append(f"🟡 Serial USB non mappé dans profiles.json: {serial}")
            logs.append("➡️ Mets ce serial dans le bon profil (onglet Profiles).")
            continue

        for pname in prof_names:
            cfg = profiles.get(pname, {}) or {}
            if not cfg.get("enabled", True):
                logs.append(f"[SKIP] Profil désactivé: {pname}")
                continue

            port = int(cfg.get("tcpip_port", 5555) or 5555)
            logs.append(f"{pname} → tcpip_port={port}")

            # 3.1) IP route (sur le même port qui voit l'USB)
            _, out_ip = adb_run(f"adb -s {serial} shell ip route", port=usb_port)
            ip = _extract_ip_from_ip_route(out_ip or "")
            logs.append("[ip route]")
            logs.append((out_ip or "").strip())

            if not ip:
                logs.append("❌ IP introuvable (le téléphone n’est peut-être pas sur le Wi-Fi).")
                continue

            logs.append(f"✅ IP: {ip}")

            # 3.2) tcpip (sur le même port USB)
            _, out_tcp = adb_run(f"adb -s {serial} tcpip {port}", port=usb_port)
            logs.append(f"[tcpip {port}]")
            logs.append((out_tcp or "").strip())

            # petite pause (le daemon redémarre en tcpip)
            time.sleep(0.6)

            # 3.3) connect Wi-Fi sur 5038 (adb_run sans port => 5038)
            _, out_conn = adb_run(f"adb connect {ip}:{port}")
            txt = (out_conn or "").strip()
            logs.append(f"[connect {ip}:{port} → 5038]")
            logs.append(txt)

            ok = ("connected" in txt.lower()) or ("already connected" in txt.lower())
            if not ok:
                logs.append("❌ adb connect KO.")
                logs.append("➡️ Causes probables :")
                logs.append("   - Téléphone redémarré (ADB Wi-Fi OFF) → refais 'Scanner & connecter'")
                logs.append("   - IP changé (nouveau Wi-Fi) → refais 'Scanner & connecter'")
                logs.append("   - Réseau d’hôtel isolé (client isolation) → ports bloqués")
                continue

            # 3.4) Mise à jour du profil + propagation
            old_id = (cfg.get("device_id") or "").strip()
            new_id = f"{ip}:{port}"

            cfg["tcpip_ip"] = ip
            cfg["tcpip_port"] = port
            cfg["device_id"] = new_id
            profiles[pname] = cfg
            profiles_changed = True

            if old_id and old_id != new_id:
                for other_name, other_cfg in profiles.items():
                    if other_name == pname:
                        continue
                    if (other_cfg.get("device_id") or "").strip() == old_id:
                        other_cfg["tcpip_ip"] = ip
                        other_cfg["tcpip_port"] = port
                        other_cfg["device_id"] = new_id
                        profiles_changed = True
                        logs.append(f"  → propagation aussi pour '{other_name}'")

            logs.append(f"✅ OK: {pname} → {new_id}")

    # ------------------------------------------------------------------
    # 4) Sauvegarde profiles.json
    # ------------------------------------------------------------------
    if profiles_changed:
        save_json(PROFILES, {"profiles": profiles})
        logs.append("\n✅ profiles.json mis à jour.")
    else:
        logs.append("\nℹ️ Rien à sauvegarder.")

    # ------------------------------------------------------------------
    # 5) État final
    # ------------------------------------------------------------------
    _, _, raw_after = scan_adb_devices(wait_seconds=1.5, poll_interval=0.3)
    logs.append("\n=== adb devices (après auto-connexion) ===")
    logs.append(raw_after)

    return "\n".join(logs)

# ==========================================================================
# 🔥 3. LIST DEVICES PRO : adb devices stylé et fusionné
# ==========================================================================

def list_devices_pro(with_ping: bool = True) -> str:

    """
    Vue PRO de l'état ADB, avec fusion des profils :

        - 🟢 CONNECTÉS (USB)
        - 🟢 CONNECTÉS (Wi-Fi)
        - 🔴 ABSENTS (Wi-Fi)
        - ⚪ DÉSACTIVÉS
        - Résumé final X / Y périphériques actifs (sans doublons)
    """
    profiles = load_profiles_dict()
    wifi_map, usb_map, disabled_map, unique_count = build_devices_mapping(profiles)

    logs: List[str] = []
    logs.append("=== ADB DEVICES (Mode PRO) ===\n")
    usb_connected, wifi_connected, out_5037, out_5038 = scan_adb_devices_fast()

    logs.append("[DEBUG] ADB 5038 raw:")
    logs.append(out_5038.strip() or "(vide)")
    logs.append("\n[DEBUG] ADB 5037 raw:")
    logs.append(out_5037.strip() or "(vide)")
    logs.append("")

    # 🟢 CONNECTÉS (USB)
    logs.append("🟢 CONNECTÉS (USB) :")
    usb_found = False

    for serial, profils in usb_map.items():
        if serial in usb_connected:
            logs.append(f"   🟢 {fusion_label(profils)} ({serial})")
            usb_found = True

    # USB inconnus (nouveaux devices)
    for serial in usb_connected:
        if serial not in usb_map:
            logs.append(f"   🟢 {serial} (nouveau périphérique USB)")
            usb_found = True

    if not usb_found:
        logs.append("   Aucun device USB connecté.")

    # 🟢 CONNECTÉS (Wi-Fi)
    logs.append("\n🟢 CONNECTÉS (Wi-Fi) :")
    wifi_found = False

    for dev_id, profils in wifi_map.items():
        if dev_id in wifi_connected:
            logs.append(f"   🟢 {fusion_label(profils)} ({dev_id})")
            wifi_found = True

    if not wifi_found:
        logs.append("   Aucun device Wi-Fi connecté.")

    # 🔴 ABSENTS (Wi-Fi)
    logs.append("\n🔴 ABSENTS (Wi-Fi) :")
    abs_found = False

    for dev_id, profils in wifi_map.items():
        if dev_id not in wifi_connected:
            ip = dev_id.split(":")[0]

            # ✅ Phase 1 : affichage instantané (pas de ping)
            if not with_ping:
                status = "Analyse réseau..."
            else:
                # ✅ Phase 2 : ping (plus lent)
                try:
                    p = Popen(["ping", "-n", "1", "-w", "300", ip], stdout=PIPE)
                    resp = p.stdout.read().decode(errors="ignore")
                    if "TTL=" in resp:
                        status = "⚡ Ping OK (ADB OFF)"
                    else:
                        status = "🔴 Hors ligne"
                except Exception:
                    status = "❓ Indéfini"

            logs.append(f"   🔴 {fusion_label(profils)} ({dev_id}) → {status}")
            abs_found = True

    if not abs_found:
        logs.append("   Aucun device absent.")

    # ⚪ DÉSACTIVÉS
    logs.append("\n⚪ DÉSACTIVÉS :")
    if disabled_map:
        for dev_id, profils in disabled_map.items():
            dev_label = dev_id or "device_id inconnu"
            logs.append(f"   ⚪ {fusion_label(profils)} ({dev_label}) → Désactivé")
    else:
        logs.append("   Aucun device désactivé.")

    # Comptage
    connected_devices_ids = set()

    # Devices connectés en Wi-Fi
    for dev_id in wifi_map.keys():
        if dev_id in wifi_connected:
            connected_devices_ids.add(dev_id)
            continue

        # Devices connectés via USB
        profils = wifi_map[dev_id]
        for prof in profils:
            serial = (profiles.get(prof, {}).get("adb_serial") or "").strip()
            if serial and serial in usb_connected:
                connected_devices_ids.add(dev_id)
                break

    total_connected = len(connected_devices_ids)
    logs.append(
        f"\n=== Résultat : {total_connected} / {unique_count} périphériques actifs ==="
    )

    return "\n".join(logs)


# ==========================================================================
# 🔥 4. Connexion PRO : connect_all_devices()
# ==========================================================================

def connect_all_devices() -> str:
    """
    Connecte tous les device_id (ip:port) configurés.
    - priorité 5038
    - si 5038 ne voit aucun ip:port, on "importe" depuis 5037 (lecture) puis connect via 5038
    """
    profiles = load_profiles_dict()
    wifi_map, _, disabled_map, unique_count = build_devices_mapping(profiles)

    logs: List[str] = []
    logs.append("=== ADB CONNECT ALL (Mode PRO) ===\n")

    adb_run("adb disconnect")  # 5038

    # ✅ si 5038 ne voit aucun wifi, on tente de "ré-importer" depuis 5037
    _, out_5038 = adb_run("adb devices")
    wifi_5038 = [s for s, st in _parse_adb_devices(out_5038) if ":" in s and st == "device" and not _is_emulator_serial(s)]

    if not wifi_5038:
        _, out_5037 = adb_run_sdk("adb devices")
        wifi_5037 = [s for s, st in _parse_adb_devices(out_5037) if ":" in s and st == "device" and not _is_emulator_serial(s)]
        for dev in wifi_5037:
            adb_run(f"adb connect {dev}")  # connect sur 5038
        if wifi_5037:
            logs.append(f"[Import] {len(wifi_5037)} device(s) importé(s) de 5037 → 5038")

    connected_ids: List[str] = []
    missing_ids: List[str] = []

    for dev_id in wifi_map.keys():
        _, outc = adb_run(f"adb connect {dev_id}")  # 5038
        txt = (outc or "").strip().lower()
        if "connected" in txt or "already connected" in txt:
            connected_ids.append(dev_id)
        else:
            missing_ids.append(dev_id)

    logs.append("🟢 CONNECTÉS (Wi-Fi) :")
    if connected_ids:
        for dev_id in connected_ids:
            profils = wifi_map.get(dev_id, [])
            logs.append(f"   🟢 {fusion_label(profils)} ({dev_id})")
    else:
        logs.append("   Aucun device connecté.")

    logs.append("\n🔴 ABSENTS (Wi-Fi) :")
    if missing_ids:
        for dev_id in missing_ids:
            profils = wifi_map.get(dev_id, [])
            ip = dev_id.split(":")[0]
            try:
                p = Popen(["ping", "-n", "1", "-w", "300", ip], stdout=PIPE)
                resp = p.stdout.read().decode(errors="ignore")
                status = "⚡ Ping OK (ADB OFF)" if "TTL=" in resp else "🔴 Hors ligne"
            except Exception:
                status = "❓ Indéfini"
            logs.append(f"   🔴 {fusion_label(profils)} ({dev_id}) → {status}")
    else:
        logs.append("   Aucun device absent.")

    logs.append("\n⚪ DÉSACTIVÉS :")
    if disabled_map:
        for dev_id, profils in disabled_map.items():
            dev_label = dev_id or "device_id inconnu"
            logs.append(f"   ⚪ {fusion_label(profils)} ({dev_label}) → Désactivé")
    else:
        logs.append("   Aucun device désactivé.")

    logs.append(f"\n=== Résultat : {len(connected_ids)} / {unique_count} périphériques Wi-Fi actifs ===")
    return "\n".join(logs)
