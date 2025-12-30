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

def launch_appium_from_bat():
    try:
        bat_path = Path(__file__).resolve().parents[1] / "Lancer_Appium_StoryFX.bat"
        subprocess.Popen(str(bat_path), shell=True)
        return True
    except Exception:
        return False


# ============================================================
# 3) ASSURER APPIUM → PORT 4723 + ADB PORT 5038
# ============================================================
def ensure_appium_running(win=None) -> bool:
    """
    SAFE: ne tue ni adb global, ni node global.
    - Assure adb StoryFX sur port 5038
    - Démarre Appium sur 4723 avec --adb-port 5038
    - Ne touche pas FormaFX (adb 5037 + émulateur)
    """

    # 1) Si Appium est déjà UP -> OK
    try:
        with socket.create_connection((APPIUM_HOST, APPIUM_PORT), timeout=0.5):
            return True
    except Exception:
        pass

    # 2) Démarrer le serveur ADB StoryFX sur 5038 (sans impacter 5037)
    env = os.environ.copy()
    env["ANDROID_ADB_SERVER_PORT"] = str(ADB_PORT_STORYFX)

    try:
        subprocess.run(
            [ADB_STORYFX, "start-server"],
            env=env,
            capture_output=True,
            text=True
        )
    except Exception as e:
        if win:
            win.write_event_value(
                "-RUNNER-LOG-",
                f"[StoryFX] [WARN] adb start-server 5038 failed: {e!r}"
            )
        # on continue quand même

    # 3) Démarrer Appium
    appium_bin = shutil.which("appium") or shutil.which("appium.cmd") or "appium"

    cmd = [
        appium_bin,
        "--allow-cors",
        "--relaxed-security",
        "--base-path", "/wd/hub",
        "--address", APPIUM_HOST,
        "--port", str(APPIUM_PORT),
        # "--adb-port", str(ADB_PORT_STORYFX),
    ]

    proc = None

    try:
        proc = subprocess.Popen(
            " ".join(cmd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
        )
    except FileNotFoundError:
        # fallback : on tente de lancer via le .bat (si 'appium' n'est pas dans le PATH)
        if launch_appium_from_bat():
            # attendre que 4723 écoute
            for _ in range(60):  # ~15s
                try:
                    with socket.create_connection((APPIUM_HOST, APPIUM_PORT), timeout=0.5):
                        return True
                except Exception:
                    time.sleep(0.25)

        msg = "[Appium] introuvable. Installe Appium ou ajoute-le au PATH (ou vérifie Lancer_Appium_StoryFX.bat)."
        if win:
            win.write_event_value("-RUNNER-LOG-", msg)
        return False

    # 4) Attendre que 4723 écoute vraiment (cas où Popen a réussi)
    for _ in range(60):  # ~15 sec
        try:
            with socket.create_connection((APPIUM_HOST, APPIUM_PORT), timeout=0.5):
                return True
        except Exception:
            time.sleep(0.25)

    # 5) Si ça ne démarre pas, on récupère quelques lignes du log Appium
    out = ""
    if proc and proc.stdout:
        try:
            for _ in range(40):
                line = proc.stdout.readline()
                if not line:
                    break
                out += line
        except Exception:
            pass

    raise RuntimeError(
        f"Appium ne démarre pas sur {APPIUM_HOST}:{APPIUM_PORT}. "
        f"Vérifie que la commande 'appium' existe et que le port n'est pas occupé.\n"
        f"--- Appium output ---\n{out}"
    )

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


def scan_adb_devices() -> Tuple[set, set, str]:
    """
    Retourne l'état ADB combiné :

        usb_serials : serials USB vus par ADB 5037 (Android Studio)
        wifi_ids    : deviceId (IP:PORT) vus par ADB 5038 (StoryFX)
        raw_output  : texte combiné pour les logs
    """
    # USB / émulateurs → serveur 5037
    _, out_usb = adb_run_sdk("adb devices")

    # Wi-Fi StoryFX → serveur 5038
    _, out_wifi = adb_run("adb devices")

    usb_serials = set()
    wifi_ids = set()

    # parse USB (5037)
    for line in out_usb.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serial = parts[0]
            if ":" not in serial:
                usb_serials.add(serial)

    # parse Wi-Fi (5038)
    for line in out_wifi.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serial = parts[0]
            if ":" in serial:
                wifi_ids.add(serial)

    raw = (
        "=== ADB 5037 (USB / émulateurs) ===\n" + out_usb.strip() +
        "\n\n=== ADB 5038 (StoryFX Wi-Fi) ===\n" + out_wifi.strip()
    )

    return usb_serials, wifi_ids, raw



# ==========================================================================
# 🔥 1. Déconnexion totale + vue PRO
# ==========================================================================

def disconnect_all_devices() -> str:
    """
    Déconnexion PRO :
        - Reset ADB (disconnect + kill-server + start-server)
        - Affichage clair et fusionné :
            • 🟢 CONNECTÉS (USB)
            • 🟢 CONNECTÉS (Wi-Fi)
            • 🔴 ABSENTS (Wi-Fi)
            • ⚪ DÉSACTIVÉS (Wi-Fi)
        - Comptage sans doublons : 1 device = 1 device_id
    """
    profiles = load_profiles_dict()
    wifi_map, usb_map, disabled_map, unique_count = build_devices_mapping(profiles)

    logs: List[str] = []
    logs.append("=== Reset ADB (Mode PRO) : déconnexion de tous les appareils ===\n")

    # Reset complet d'ADB
    adb_run("adb disconnect")
    adb_run("adb kill-server")
    code, out = adb_run("adb start-server")
    logs.append(out.strip())

    # Lecture de l'état ADB après reset
    usb_connected, wifi_connected, _ = scan_adb_devices()

    # 🟢 CONNECTÉS (USB)
    logs.append("\n🟢 CONNECTÉS (USB) :")
    found_usb = False

    # 1) USB connus (déclarés dans profiles.json)
    for serial, profils in usb_map.items():
        if serial in usb_connected:
            logs.append(f"   🟢 {fusion_label(profils)} ({serial})")
            found_usb = True

    # 2) USB inconnus (nouveaux devices non encore déclarés)
    for serial in usb_connected:
        if serial not in usb_map:
            logs.append(f"   🟢 {serial} (nouveau périphérique USB)")
            found_usb = True

    if not found_usb:
        logs.append("   Aucun device USB connecté.")

    # 🟢 CONNECTÉS (Wi-Fi)
    logs.append("\n🟢 CONNECTÉS (Wi-Fi) :")
    found_wifi = False

    for dev_id, profils in wifi_map.items():
        if dev_id in wifi_connected:
            logs.append(f"   🟢 {fusion_label(profils)} ({dev_id})")
            found_wifi = True

    if not found_wifi:
        logs.append("   Aucun device Wi-Fi connecté.")

    # 🔴 ABSENTS (Wi-Fi uniquement, fusionnés)
    logs.append("\n🔴 ABSENTS (Wi-Fi) :")
    absent = False
    for dev_id, profils in wifi_map.items():
        if dev_id not in wifi_connected:
            logs.append(f"   🔴 {fusion_label(profils)} ({dev_id}) → Hors ligne")
            absent = True
    if not absent:
        logs.append("   Aucun device absent.")

    # ⚪ DÉSACTIVÉS
    logs.append("\n⚪ DÉSACTIVÉS :")
    if disabled_map:
        for dev_id, profils in disabled_map.items():
            label = fusion_label(profils)
            dev_label = dev_id or "device_id inconnu"
            logs.append(f"   ⚪ {label} ({dev_label}) → Désactivé")
    else:
        logs.append("   Aucun device désactivé.")

    # Comptage : un device = un device_id
    # On considère qu'un device est "actif" s'il est connecté en Wi-Fi OU
    # si au moins un de ses profils a un serial USB connecté.
    connected_devices_ids = set()

    # Devices connectés en Wi-Fi
    for dev_id in wifi_map.keys():
        if dev_id in wifi_connected:
            connected_devices_ids.add(dev_id)
            continue

        # Devices connectés EN USB via l'un de leurs profils
        profils = wifi_map[dev_id]
        for prof_name in profils:
            serial = (profiles.get(prof_name, {}).get("adb_serial") or "").strip()
            if serial and serial in usb_connected:
                connected_devices_ids.add(dev_id)
                break

    total_connected = len(connected_devices_ids)

    logs.append(
        f"\n=== Résultat : {total_connected} / {unique_count} périphériques actifs ==="
    )

    return "\n".join(logs)


# ==========================================================================
# 🔥 2. Auto-connexion USB → Wi-Fi complète
# ==========================================================================

def auto_connect_all_devices(profiles: Dict[str, Dict[str, Any]]) -> str:
    """
    Auto-connexion complète (USB → Wi-Fi) :

        1. Lit l'état ADB :
            - USB via serveur 5037 (Android Studio) → adb_run_sdk
            - Wi-Fi via serveur 5038 (StoryFX)      → adb_run
        2. Liste les serials USB connectés.
        3. Pour chaque serial USB :
            - détecte l'IP via 'adb -s <serial> shell ip route' (5037)
            - bascule le téléphone en 'tcpip <port>' (5037)
            - se connecte en 'adb connect ip:port' (5038)
            - met à jour profiles.json :
                tcpip_ip, tcpip_port, device_id (ip:port)
            - propage ce nouveau device_id aux autres profils liés.
        4. Affiche l'état ADB final après auto-connexion.
    """
    global LAST_USB_SERIALS

    logs: List[str] = []
    logs.append("=== Auto-connexion ADB (USB → Wi-Fi) ===")

    # 1) Charger les profils frais
    profiles = load_profiles_dict()
    name_map = build_device_name_map(profiles)

    # 2) adb devices initial : USB (5037) + Wi-Fi (5038)
    usb_serials, _, raw = scan_adb_devices()

    # Mise en forme avec labels lisibles
    formatted = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serial = parts[0]
            label = name_map.get(serial, "")
            if label:
                formatted.append(f"{serial}\tdevice\t→ {label}")
            else:
                formatted.append(line)
        else:
            formatted.append(line)

    logs.append("\n".join(formatted))

    # 3) serials USB uniquement (sans ip:port)
    serials_usb = sorted(s for s in usb_serials if ":" not in s)
    LAST_USB_SERIALS = serials_usb[:]  # pour le bouton "Copier serial(s)"

    if not serials_usb:
        logs.append("Aucun appareil USB détecté.")
        return "\n".join(logs)

    # 4) index serial -> profils liés
    adb_index = _build_adb_index(profiles)
    profiles_changed = False

    # 5) boucle sur chaque serial USB
    for serial in serials_usb:
        logs.append(f"\n--- {serial} ---")

        prof_names = adb_index.get(serial)
        if not prof_names:
            logs.append(f"→ Aucun profil avec adb_serial='{serial}'")
            continue

        for pname in prof_names:
            cfg = profiles.get(pname, {})
            if not cfg.get("enabled", True):
                logs.append(f"[SKIP] Profil {pname} désactivé.")
                continue

            port = int(cfg.get("tcpip_port", 5555) or 5555)
            logs.append(f"{pname} → détection IP & tcpip {port}")

            # 1) détecter l'IP via ip route → ADB 5037
            code_ip, out_ip = adb_run_sdk(f"adb -s {serial} shell ip route")
            logs.append("[ip route]")
            logs.append(out_ip.strip())

            ip = _extract_ip_from_ip_route(out_ip)
            if not ip:
                logs.append("!! IP introuvable (ip route)")
                continue

            logs.append(f"IP détectée : {ip}")

            # 2) passer en tcpip <port> → ADB 5037
            adb_run_sdk(f"adb -s {serial} tcpip {port}")

            # 3) connect ip:port → ADB 5038 (StoryFX)
            _, out_conn = adb_run(f"adb connect {ip}:{port}")
            logs.append(out_conn.strip())

            # 4) mise à jour du profil
            old_id = cfg.get("device_id")
            new_id = f"{ip}:{port}"

            cfg["tcpip_ip"] = ip
            cfg["tcpip_port"] = port
            cfg["device_id"] = new_id
            profiles_changed = True

            # propagation aux autres profils qui utilisaient l'ancien device_id
            if old_id:
                for other_name, other_cfg in profiles.items():
                    if other_name == pname:
                        continue
                    if (other_cfg.get("device_id") or "").strip() == old_id:
                        other_cfg["tcpip_ip"] = ip
                        other_cfg["tcpip_port"] = port
                        other_cfg["device_id"] = new_id
                        profiles_changed = True
                        logs.append(
                            f"  → propagation aussi pour '{other_name}'"
                        )

    # 6) sauvegarde des profils si modifiés
    if profiles_changed:
        save_json(PROFILES, {"profiles": profiles})
        logs.append("\nProfils mis à jour (IP/port/device_id).")

    # 7) état final des devices après auto-connexion
    usb_after, wifi_after, raw_after = scan_adb_devices()
    formatted_after = []
    name_map = build_device_name_map(profiles)

    for line in raw_after.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serial = parts[0]
            label = name_map.get(serial, "")
            if label:
                formatted_after.append(f"{serial}\tdevice\t→ {label}")
            else:
                formatted_after.append(line)
        else:
            formatted_after.append(line)

    logs.append("\n=== adb devices (après auto-connexion) ===")
    logs.append("\n".join(formatted_after))

    return "\n".join(logs)



# ==========================================================================
# 🔥 3. LIST DEVICES PRO : adb devices stylé et fusionné
# ==========================================================================

def list_devices_pro() -> str:
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

    usb_connected, wifi_connected, _ = scan_adb_devices()

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
            # ping pour donner plus d'info
            ip = dev_id.split(":")[0]
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
    Connexion PRO de tous les devices configurés (Wi-Fi) :

        - Déconnecte tous les devices ADB.
        - Tente 'adb connect <device_id>' pour chaque device_id unique.
        - Affiche :
            🟢 CONNECTÉS (Wi-Fi)
            🔴 ABSENTS (Wi-Fi, avec ping)
            ⚪ DÉSACTIVÉS
        - Résumé final X / Y périphériques Wi-Fi actifs.
    """
    profiles = load_profiles_dict()
    wifi_map, _, disabled_map, unique_count = build_devices_mapping(profiles)

    logs: List[str] = []
    logs.append("=== ADB CONNECT ALL (Mode PRO) ===\n")

    # Déconnecter tout pour partir sur une base propre
    adb_run("adb disconnect")

    connected_ids: List[str] = []
    missing_ids: List[str] = []

    # Tentative de connexion pour chaque device_id unique
    for dev_id in wifi_map.keys():
        code, outc = adb_run(f"adb connect {dev_id}")
        txt = outc.strip().lower()
        if "connected" in txt or "already connected" in txt:
            connected_ids.append(dev_id)
        else:
            missing_ids.append(dev_id)

    # 🟢 CONNECTÉS
    logs.append("🟢 CONNECTÉS (Wi-Fi) :")
    if connected_ids:
        for dev_id in connected_ids:
            profils = wifi_map.get(dev_id, [])
            logs.append(f"   🟢 {fusion_label(profils)} ({dev_id})")
    else:
        logs.append("   Aucun device connecté.")

    # 🔴 ABSENTS + ping
    logs.append("\n🔴 ABSENTS (Wi-Fi) :")
    if missing_ids:
        for dev_id in missing_ids:
            profils = wifi_map.get(dev_id, [])
            ip = dev_id.split(":")[0]
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
    else:
        logs.append("   Aucun device absent.")

    # ⚪ DÉSACTIVÉS
    logs.append("\n⚪ DÉSACTIVÉS :")
    if disabled_map:
        for dev_id, profils in disabled_map.items():
            dev_label = dev_id or "device_id inconnu"
            logs.append(f"   ⚪ {fusion_label(profils)} ({dev_label}) → Désactivé")
    else:
        logs.append("   Aucun device désactivé.")

    logs.append(
        f"\n=== Résultat : {len(connected_ids)} / {unique_count} périphériques Wi-Fi actifs ==="
    )

    return "\n".join(logs)
