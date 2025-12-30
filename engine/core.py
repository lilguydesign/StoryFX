# -*- coding: utf-8 -*-
"""
Core helpers partagés par les engines StoryFX.
Centralise ADB / Appium + actions réutilisables dans la Galerie.
"""
from ui.ui_devices import ensure_appium_running
import time
import subprocess
import traceback
import json                    # ✅ AJOUTER CETTE LIGNE
from typing import Optional
import sys
import os
from datetime import datetime

import re

import winsound

from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.extensions.android.nativekey import AndroidKey



from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from appium.webdriver.common.touch_action import TouchAction
from pathlib import Path  # en haut du fichier si pas déjà importé
try:
    from appium.options.android import UiAutomator2Options
except Exception:
    UiAutomator2Options = None

ADB_PATH = r"C:\Tools\ADB_StoryFX\adb.exe"
ADB_ENV = os.environ.copy()
ADB_ENV["ANDROID_ADB_SERVER_PORT"] = "5038"


def clear_popups_and_go_home(driver):
    """Nettoie les popups (USSD/MMI, rappels…) puis revient à l'accueil."""

    # 1) Essayer de cliquer sur un bouton 'OK' / 'Dismiss' si présent
    try:
        candidates = driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR,
            'new UiSelector().textContains("OK")'
        )
        if candidates:
            candidates[0].click()
    except Exception:
        pass

    # 2) Envoyer plusieurs BACK pour être sûr de fermer tous les overlays
    for _ in range(3):
        try:
            driver.press_keycode(AndroidKey.BACK)
        except Exception:
            try:
                driver.back()
            except Exception:
                break
        time.sleep(0.2)

    # 3) HOME pour revenir à la page d'accueil
    try:
        driver.press_keycode(AndroidKey.HOME)
    except Exception:
        pass


def open_gallery(driver):
    """Ouvre la galerie Samsung en partant de l'accueil."""
    driver.activate_app("com.sec.android.gallery3d")

def adb_swipe_unlock(device_id: str):
    """
    Déverrouille l'écran via ADB pour les lockscreens du type 'Swipe to open'.
    - Réveille l'écran
    - Récupère la résolution (wm size)
    - Fait un swipe bas -> haut au centre de l'écran
    """
    device_id = (device_id or "").strip()
    if not device_id:
        return

    try:
        log(f"[Screen][ADB] Tentative de swipe unlock sur {device_id}...")

        # 1) Réveiller l'écran (KEYCODE_WAKEUP = 224)
        try:
            subprocess.run(
                [ADB_PATH, "-s", device_id, "shell", "input", "keyevent", "224"],
                check=False,
                env=ADB_ENV,
            )
        except Exception as exc:
            log(f"[Screen][ADB][WARN] keyevent 224 a échoué : {exc!r}")

        time.sleep(0.8)

        # 2) Récupérer la taille de l'écran
        try:
            proc = subprocess.run(
                [ADB_PATH, "-s", device_id, "shell", "wm", "size"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=ADB_ENV,
            )
            out = proc.stdout or ""
            m = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
            if m:
                w = int(m.group(1))
                h = int(m.group(2))
                x = w // 2
                start_y = int(h * 0.85)
                end_y   = int(h * 0.25)
            else:
                # fallback générique
                x, start_y, end_y = 500, 1600, 400
                log(f"[Screen][ADB][WARN] wm size introuvable, fallback swipe ({x},{start_y}->{x},{end_y})")
        except Exception as exc:
            log(f"[Screen][ADB][WARN] Impossible de lire wm size : {exc!r}")
            x, start_y, end_y = 500, 1600, 400

        # 3) Swipe bas → haut
        try:
            subprocess.run(
                [
                    ADB_PATH, "-s", device_id,
                    "shell", "input", "swipe",
                    str(x), str(start_y), str(x), str(end_y), "800"
                ],
                check=False,
                env=ADB_ENV,
            )
            time.sleep(0.8)
            log("[Screen][ADB] Swipe unlock envoyé.")
        except Exception as exc:
            log(f"[Screen][ADB][WARN] Erreur pendant input swipe : {exc!r}")

    except Exception as exc:
        log(f"[Screen][ADB][WARN] Erreur globale adb_swipe_unlock : {exc!r}")


def is_storyfx_serial(serial: str) -> bool:
    """
    Retourne True si le device doit être utilisé par StoryFX.

    Règles :
    - doit contenir ":" (ip:port, ex: 192.168.1.123:5555)
    - NE doit PAS contenir "emulator"
    - NE doit PAS contenir "5554"
    """
    if not serial:
        return False

    s = serial.strip().lower()

    if "emulator" in s:
        return False
    if "5554" in s:
        return False

    return ":" in s

# ------------------------------------------------------------------ #
# LOG / ADB
# ------------------------------------------------------------------ #
def log(msg: str) -> None:
    """Affiche un log simple (ASCII) pour éviter les problèmes d'encodage."""
    # Si le scheduler nous fournit une heure de rattrapage, on l'utilise
    ts_env = os.environ.get("STORYFX_TIME")
    if ts_env:
        ts = ts_env
    else:
        ts = datetime.now().strftime("%H:%M:%S")

    print(f"[StoryFX] {ts} | {msg}", flush=True)



def adb_devices_text():
    """
    Exécute adb devices et filtre l'émulateur.
    """
    try:
        out = subprocess.check_output(
            [ADB_PATH, "devices"],
            env=ADB_ENV,
            stderr=subprocess.STDOUT,
            text=True
        )
    except Exception as exc:
        return f"[ADB ERROR] {exc}"

    # On supprime toutes les lignes emulator-5554
    filtered = []
    for line in out.splitlines():
        if "emulator" in line.lower():
            continue
        if "5554" in line:
            continue
        filtered.append(line)

    return "\n".join(filtered) + "\n"


def adb_devices_filtered_text() -> str:
    """
    Retourne la liste adb devices filtrée pour StoryFX :
    - on ne garde que les serials valides (voir is_storyfx_serial)
    - on ignore les lignes "emulator-5554", USB, etc.
    """
    raw = adb_devices_text()
    lines = []

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue

        parts = line.split()
        serial = parts[0] if parts else ""

        if not is_storyfx_serial(serial):
            # on ignore les émulateurs / usb / serials bizarres
            continue

        lines.append(line)

    if not lines:
        return "List of StoryFX devices:\n  (aucun device valide)\n"

    return "List of StoryFX devices:\n" + "\n".join(f"  {l}" for l in lines) + "\n"

def ensure_adb_connected(device_id: str) -> bool:
    """
    Force ADB à n'avoir qu'UN SEUL device réseau actif :
      - adb disconnect  (tous les devices ip:port)
      - adb connect <device_id>  (ex: 192.168.1.123:5555)

    Si device_id ne contient pas ":", on reste sur l'ancien comportement
    (cas d'un serial USB brut).
    """
    device_id = (device_id or "").strip()


    # Si le device_id lui-même ne respecte pas les règles, on le rejette
    if not is_storyfx_serial(device_id):
        log(f"[WARN] Device id '{device_id}' rejeté (non ip:port ou emulator/5554).")
        return False

    # Cas classique StoryFX : device_id = "ip:port"
    if ":" in device_id:
        log(f"ADB reset : déconnexion de tous les devices puis connexion sur {device_id} ...")

        # 1) on vide toutes les connexions réseau
        try:
            subprocess.run([ADB_PATH, "disconnect"], check=False, env=ADB_ENV)
        except Exception as exc:
            log(f"[WARN] adb disconnect a échoué : {exc!r}")

        time.sleep(0.5)

        # 2) on connecte UNIQUEMENT le device cible
        try:
            subprocess.run([ADB_PATH, "connect", device_id], check=False, env=ADB_ENV)
        except Exception as exc:
            log(f"[WARN] adb connect {device_id} a échoué : {exc!r}")

        time.sleep(1.0)

        # 🔥 on log maintenant la version filtrée
        filtered = adb_devices_filtered_text()
        log(filtered.strip())

        # et on vérifie uniquement dans la liste filtrée
        if device_id in filtered:
            log(f"ADB connection OK sur {device_id}")

            # 🔥 Déverrouillage ADB pour les lockscreens type "Swipe to open"
            adb_swipe_unlock(device_id)

            return True

        log(f"[WARN] ADB device {device_id} non connecté après reset.")
        return False

    # Cas plus rare : device_id est un serial USB (sans ip:port)
    out = adb_devices_text()
    if device_id and device_id in out:
        log(f"ADB already connected (USB) : {device_id}")
        return True

    log(f"Device id '{device_id}' is not of form ip:port, cannot auto-connect.")
    return False

# ------------------------------------------------------------------ #
# APPIUM DRIVER
# ------------------------------------------------------------------ #
def unmute_and_volume_80():
    """
    Désactive le mute et met le volume système à ~80% sous Windows
    via NirCmd. Ne plante jamais même si NirCmd n'existe pas.
    """
    try:
        if sys.platform.startswith("win"):
            # ⚠️ Mets ici ton vrai chemin vers nircmd.exe
            nircmd_path = r"C:\Tools\nircmd\nircmd.exe"

            # Unmute
            subprocess.run(
                [nircmd_path, "mutesysvolume", "0"],
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            # Volume ~80% (65535 * 0.8 ≈ 52428)
            subprocess.run(
                [nircmd_path, "setsysvolume", "52428"],
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

    except Exception:
        # On ne veut pas planter si on ne peut pas changer le volume
        pass


def play_critical_sound():
    """
    Joue un son d'erreur personnalisé (WAV) sous Windows,
    ou un simple beep sur les autres OS.
    """
    try:
        if sys.platform.startswith("win"):
            import winsound
            from pathlib import Path

            # Chemin vers StoryFx/assets/storyfx_error_alert.wav
            base_dir = Path(__file__).resolve().parent.parent  # .../StoryFx/engine -> parent = StoryFx
            wav_path = base_dir / "assets" / "storyfx_error_alert.wav"

            if wav_path.exists():
                winsound.PlaySound(str(wav_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                # fallback : son système Windows
                winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
        else:
            # Beep console (Linux / macOS)
            print("\a", end="", flush=True)

    except Exception:
        # Ne jamais planter à cause du son
        pass



def make_driver(device_id: str, platform_version: Optional[str] = None, profile: dict | None = None):
    caps = {
        "platformName": "Android",
        "deviceName": device_id,
        "automationName": "UiAutomator2",
        "noReset": True,
        "autoGrantPermissions": True,
        "newCommandTimeout": 180,
        "appPackage": "com.sec.android.gallery3d",
        "appActivity": "com.sec.android.gallery3d.app.GalleryActivity",
    }

    # ✅ Personnalisation par profil (FRONT) pour la Galerie
    gal = (profile or {}).get("gallery", {}) or {}
    if isinstance(gal, dict):
        pkg = (gal.get("appPackage") or "").strip()
        act = (gal.get("appActivity") or "").strip()
        if pkg:
            caps["appPackage"] = pkg
        if act:
            caps["appActivity"] = act

    if platform_version:
        caps["platformVersion"] = str(platform_version)

    # ✅ Overides par profil (venant du FRONT via profiles.json)
    overrides = (profile or {}).get("appium_overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}

    log("Creating Appium driver ...")
    server_url = "http://127.0.0.1:4723/wd/hub"

    try:
        if UiAutomator2Options is not None:
            options = UiAutomator2Options().load_capabilities(caps)

            # tes defaults
            options.set_capability("appium:adbExecTimeout", 200000)
            options.set_capability("appium:adbPort", 5038)
            options.set_capability("appium:adbPath", r"C:\Tools\ADB_StoryFX\adb.exe")
            options.set_capability("appium:adbExec", r"C:\Tools\ADB_StoryFX\adb.exe")
            options.set_capability("appium:ignoreHiddenApiPolicyError", True)
            options.set_capability("appium:disableWindowAnimation", True)

            # ✅ appliquer les overrides (S20/S23/etc.)
            for k, v in overrides.items():
                options.set_capability(f"appium:{k}", v)

            ensure_appium_running()
            driver = webdriver.Remote(server_url, options=options)
        else:
            driver = webdriver.Remote(server_url, desired_capabilities=caps)

        log("Driver created OK.")

        # 🔥 Nettoyage visuel + retour Galerie AVANT de continuer StoryFX
        try:
            clear_popups_and_go_home(driver)
            open_gallery(driver)
        except Exception as e:
            log(f"[WARN] Impossible de nettoyer l'écran / ouvrir la Galerie : {e!r}")

        return driver

    except Exception:
        log("[StoryFX] [ERROR] Failed to create driver :")
        traceback.print_exc()   # même niveau de détails que dans VS Code

        # 🔊 Forcer le volume puis jouer le son d’alerte
        try:
            unmute_and_volume_80()
        except Exception:
            log("[StoryFX] [WARN] Unable to change system volume on error.")

        try:
            play_critical_sound()
        except Exception:
            log("[StoryFX] [WARN] Unable to play critical sound on error.")

        # Message très clair dans les logs
        log(
            "[StoryFX] [ALERTE] Problème Appium/UiAutomator2. "
            "Redémarre le téléphone et Appium Server."
        )

        # On relance l’exception pour ne rien cacher
        raise


_LOCATORS_CACHE = None

def load_locators():
    global _LOCATORS_CACHE
    if _LOCATORS_CACHE is None:
        loc_path = Path(__file__).resolve().parent.parent / "locators.json"
        if loc_path.exists():
            _LOCATORS_CACHE = json.loads(loc_path.read_text(encoding="utf-8"))
        else:
            _LOCATORS_CACHE = {}
    return _LOCATORS_CACHE

def get_locator(platform: str, key: str, profile_name: str | None = None) -> str | None:
    locs = load_locators()
    plat_cfg = locs.get(platform, {})
    key_cfg  = plat_cfg.get(key, {})

    if profile_name and profile_name in key_cfg:
        return key_cfg[profile_name]
    return key_cfg.get("default")

def unlock_screen_if_needed(driver):
    """
    Déverrouille l'écran si nécessaire.

    Stratégie :
      1) Réveille l'écran
      2) Fait plusieurs swipes bas → haut (lockscreen simple / vidéo "Swipe to open")
      3) Si l'écran est encore verrouillé → saisit le code PIN 233623
    """
    PASSWORD = "233623"

    try:
        log("[Screen] Vérification de l'état de l'écran...")

        # On essaie jusqu'à 3 fois (utile si l'animation du lockscreen est lente)
        for attempt in range(1, 4):
            try:
                locked = driver.is_locked()
            except Exception:
                # certains lockscreens vidéo répondent mal, on suppose verrouillé au 1er tour
                locked = (attempt == 1)

            if not locked:
                log("[Screen] Écran déjà déverrouillé.")
                return

            log(f"[Screen] Écran verrouillé → tentative de déverrouillage (essai {attempt}/3).")

            # 1) Réveiller l'écran (Power ON)
            try:
                driver.press_keycode(224)  # WAKEUP
            except Exception:
                pass
            time.sleep(1.0)

            # 2) Swipes bas → haut pour passer les lockscreens simples / vidéos
            try:
                size = driver.get_window_size()
                x = size["width"] // 2

                swipe_configs = [
                    (0.85, 0.25, 700),
                    (0.90, 0.20, 800),
                ]

                for sy, ey, dur in swipe_configs:
                    start_y = int(size["height"] * sy)
                    end_y   = int(size["height"] * ey)
                    try:
                        driver.swipe(x, start_y, x, end_y, dur)
                        time.sleep(0.7)
                    except Exception as e_sw:
                        log(f"[Screen][WARN] Erreur swipe unlock: {e_sw!r}")
            except Exception as e_sz:
                log(f"[Screen][WARN] Impossible de récupérer la taille écran: {e_sz!r}")

            time.sleep(1.0)

            # 3) Re-vérifier : peut-être que le swipe a suffi
            try:
                if not driver.is_locked():
                    log("[Screen] ✔ Écran déverrouillé par swipe.")
                    return
            except Exception:
                # on continue sur le PIN
                pass

            # 4) Si toujours verrouillé → tenter le code PIN 233623
            log("[Screen] Toujours verrouillé après swipe → tentative PIN 233623...")
            try:
                # Sur beaucoup d'appareils, la touche MENU 82 réveille / affiche le PIN si besoin
                try:
                    driver.press_keycode(82)
                    time.sleep(0.5)
                except Exception:
                    pass

                for digit in PASSWORD:
                    kc = 7 + int(digit)  # keycodes 7-16 = 0-9
                    driver.press_keycode(kc)
                    time.sleep(0.15)

                # ENTER pour valider le PIN (au cas où)
                try:
                    driver.press_keycode(66)  # ENTER
                except Exception:
                    pass

                time.sleep(1.5)

                try:
                    if not driver.is_locked():
                        log("[Screen] ✔ Écran déverrouillé par code PIN.")
                        return
                except Exception:
                    # si is_locked plante, on laisse la boucle faire un autre essai
                    pass

            except Exception as e_pin:
                log(f"[Screen][WARN] Erreur pendant la saisie PIN : {e_pin!r}")

        # Si on est encore là → échec après 3 essais
        log("[Screen] ❌ Impossible de déverrouiller l’écran après plusieurs tentatives.")
        beep_error()

    except Exception as e:
        log(f"[Screen][WARN] Erreur globale pendant le déverrouillage : {e!r}")

# ------------------------------------------------------------------ #
# GALERIE SAMSUNG
# ------------------------------------------------------------------ #

def reset_gallery_home(driver) -> bool:
    """
    Remet la Galerie dans un état propre avant un run StoryFX.

    - kill Galerie
    - kill WhatsApp / WhatsApp Business
    - kill Facebook / Messenger
    - kill Instagram
    - kill TikTok
    - relance Galerie
    - tente d'aller sur l'onglet Albums
    """
    log("Reset Gallery : kill apps + relance Galerie + onglet Albums...")

    # 1) Fermer les apps pour éviter les écrans coincés (share sheet, WhatsApp, FB, IG, TikTok, etc.)
    PACKAGE_IDS = [
        "com.sec.android.gallery3d",   # Galerie Samsung
        # "com.whatsapp.w4b",            # WhatsApp Business
        # "com.whatsapp",                # WhatsApp normal
        "com.facebook.katana",         # Facebook
        "com.facebook.orca",           # Messenger
        "com.instagram.android",       # Instagram
        "com.zhiliaoapp.musically",    # TikTok (package principal)
        # "com.ss.android.ugc.trill",   # (optionnel) autre package TikTok selon régions
    ]

    for pkg in PACKAGE_IDS:
        try:
            driver.terminate_app(pkg)
            log(f"App terminée : {pkg}")
        except Exception:
            pass

    # 2) Relancer proprement la Galerie puis aller sur l’onglet Albums
    if not start_gallery(driver):
        return False
    for _ in range(3):
        if tap_albums_tab(driver):
            return True
        try:
            driver.back()
        except Exception:
            pass
        time.sleep(0.5)

    log("[ERROR] Impossible de revenir sur la vue Albums après reset.")
    return False

def start_gallery(driver) -> bool:
    """S'assure que la Galerie est au premier plan."""
    log("Trying activate_app('com.sec.android.gallery3d') ...")
    try:
        driver.activate_app("com.sec.android.gallery3d")
        time.sleep(1.5)
        log(f"Current package after activate_app: {driver.current_package}")
        return True
    except Exception:
        log("[WARN] activate_app failed, trying start_activity fallbacks ...")
        traceback.print_exc()

    candidates = [
        ("com.sec.android.gallery3d", "com.samsung.android.gallery.app.activity.GalleryActivity"),
        ("com.sec.android.gallery3d", "com.sec.android.gallery3d.app.GalleryActivity"),
        ("com.sec.android.gallery3d", "com.sec.android.gallery3d.activity.GalleryActivity"),
    ]
    for pkg, act in candidates:
        try:
            log(f"Trying start_activity({pkg}, {act}) ...")
            driver.start_activity(pkg, act)
            time.sleep(1.5)
            log(f"Current package: {driver.current_package}")
            return True
        except Exception:
            traceback.print_exc()

    log("Unable to start Samsung Gallery after all attempts.")
    return False


# --- Petit helper pour le son d’alerte ---
if sys.platform == "win32":
    import winsound

    def alert_beep():
        # fréquence 1000 Hz, durée 600 ms
        winsound.Beep(1000, 600)
else:
    def alert_beep():
        # fallback simple sur les autres OS
        print("\a", end="", flush=True)

from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def tap_albums_tab(driver, timeout: float = 5.0) -> bool:
    """
    Clique sur l’onglet Albums dans la Galerie Samsung.

    Ordre des essais :
      1) XPATH robustes (content-desc + resource-id liés à "Albums")
      2) Fallback UiSelector (Album / Albums)
      3) Dernière chance : icône globale [2]
    """

    # 1) XPATH principaux et robustes
    xpaths = [
        # LinearLayout complet de l’onglet Albums
        '//android.widget.LinearLayout[@content-desc="Albums"]/android.view.ViewGroup',
        '//android.widget.LinearLayout[@content-desc="Albums"]',

        # Titre "Albums" dans la barre du bas
        '//android.widget.TextView[@resource-id="com.sec.android.gallery3d:id/title" and @text="Albums"]',

        # Icône à l’intérieur de l’onglet Albums (sans index global)
        '//android.widget.LinearLayout[@content-desc="Albums"]//android.widget.ImageView',

        # Anciens sélecteurs plus larges
        "//*[@resource-id='com.sec.android.gallery3d:id/tab_albums']",
        "//*[@content-desc='Albums' or contains(@content-desc,'Album') or contains(@content-desc,'Albums')]",
        "//*[@text='Albums' or @text='Album' or contains(@text,'Albums') or contains(@text,'Album')]",
    ]

    # --- Essais XPATH robustes ---
    for xp in xpaths:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((AppiumBy.XPATH, xp))
            )
            el.click()
            time.sleep(0.6)
            return True
        except Exception:
            pass

    # 2) Fallback UiSelector (texte / description, avec ou sans "s")
    ui_selectors = [
        'new UiSelector().text("Albums")',
        'new UiSelector().text("Album")',
        'new UiSelector().textContains("Albums")',
        'new UiSelector().textContains("Album")',
        'new UiSelector().descriptionContains("Albums")',
        'new UiSelector().descriptionContains("Album")',
    ]

    for ui in ui_selectors:
        try:
            driver.find_element(AppiumBy.ANDROID_UIAUTOMATOR, ui).click()
            time.sleep(0.6)
            return True
        except Exception:
            pass

    # 3) Dernière chance : icône 2e position dans la barre (fragile mais utile en secours)
    try:
        el = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                AppiumBy.XPATH,
                '(//android.widget.ImageView[@resource-id="com.sec.android.gallery3d:id/icon"])[2]'
            ))
        )
        el.click()
        time.sleep(0.6)
        return True
    except Exception:
        log("Could not tap Albums tab (all strategies failed).")
        return False



def open_album(driver, name: str, max_scrolls: int = 8) -> bool:
    """Ouvre un album par son nom, en scrollant si besoin."""
    for _ in range(max_scrolls):
        try:
            driver.find_element(
                AppiumBy.XPATH,
                f"//android.widget.TextView[@text='{name}']"
            ).click()
            time.sleep(0.8)
            log(f"Album '{name}' ouvert.")
            return True
        except Exception:
            # scroll down
            size = driver.get_window_size()
            start_y = int(size["height"] * 0.75)
            end_y = int(size["height"] * 0.25)
            x = int(size["width"] * 0.5)
            driver.swipe(x, start_y, x, end_y, 900)
            time.sleep(0.3)
    log(f"[ERROR] Album '{name}' not found after {max_scrolls} scrolls.")
    traceback.print_exc()
    return False

def long_press_first_thumb(driver, retries: int = 1) -> bool:
    """
    Active la multi-sélection via un long-press sur la première vignette,
    PUIS désélectionne cette vignette pour ne pas la compter dans le total.

    - on trouve la 1ʳᵉ vignette via thumbnail_preview_layout
    - on fait un click-and-hold (W3C Actions) puis release
    - ensuite on re-clique la même vignette pour l'enlever de la sélection
    Si ça ne lève pas d'exception → on considère que c'est OK.
    """

    xpath_first_thumb = (
        "(//android.widget.FrameLayout[@resource-id="
        "'com.sec.android.gallery3d:id/thumbnail_preview_layout'])[1]"
    )

    for attempt in range(1, retries + 1):
        try:
            log(f"[multi] Tentative long-press {attempt}/{retries}...")

            # 1) trouver la première vignette
            thumb = driver.find_element(AppiumBy.XPATH, xpath_first_thumb)
            log("[multi] Première vignette trouvée via XPATH historique.")

            # 2) long press pour activer la multi-sélection
            actions = ActionChains(driver)
            actions.click_and_hold(thumb).pause(1.0).release(thumb).perform()
            time.sleep(0.8)

            log("[multi] ✔ Long-press effectué, mode multi activé.")

            # 3) Désélectionner la première vignette pour que la sélection
            #    suivante soit 100 % aléatoire, sans imposer la première image
            try:
                thumb = driver.find_element(AppiumBy.XPATH, xpath_first_thumb)
                thumb.click()
                time.sleep(0.3)
                log("[multi] Première vignette désélectionnée (on repart de 0 sélection).")
            except Exception as e:
                # Ce n'est pas bloquant : au pire on garde la 1ʳᵉ image sélectionnée
                log(f"[multi][WARN] Impossible de désélectionner la première vignette : {e!r}")

            return True

        except Exception as e:
            log(f"[multi] ❌ Erreur long-press : {e}")
            time.sleep(0.8)

    # Si on arrive ici => toutes les tentatives ont échoué
    beep_error()
    return False


def select_first_video_then_share(driver) -> bool:
    """
    Flow minimal pour l’engine INTRO :
    - ouvre la première vignette de l’album
    - clique sur le bouton Share
    """
    try:
        # 👉 même XPath que dans tes scripts "Never_Give_Up" / "Hurry"
        first = driver.find_element(
            AppiumBy.XPATH,
            "(//android.widget.FrameLayout[@resource-id="
            "'com.sec.android.gallery3d:id/thumbnail_preview_layout'])[1]"
        )
        first.click()
        time.sleep(0.5)
        log("Première vignette ouverte avec succès.")
    except Exception:
        log("[ERROR] Could not open first thumbnail (thumbnail_preview_layout).")
        traceback.print_exc()     # stacktrace détaillée comme dans VS Code
        return False

    if not tap_share_button(driver):
        log("[ERROR] tap_share_button() failed après l’ouverture de la vidéo.")
        return False

    return True


def tap_share_button(driver) -> bool:
    """
    Essaie plusieurs XPaths pour le bouton Share dans la Galerie.

    Ordre :
      0) XPath personnalisé depuis locators.json (platform='Gallery', key='share')
      1) Liste de XPaths "classiques" (fallback)
    """
    import traceback

    tried_xpaths = []

    # 0) XPath personnalisé depuis locators.json
    custom_xp = get_locator("Gallery", "share")
    if custom_xp:
        tried_xpaths.append(custom_xp)
        try:
            el = driver.find_element(AppiumBy.XPATH, custom_xp)
            el.click()
            time.sleep(0.8)
            log(f"Share button clicked with CUSTOM XPath: {custom_xp}")
            return True
        except Exception as e:
            log(f"[WARN] Custom Share XPath KO: {custom_xp!r} ({e!r})")

    # 1) Fallbacks classiques
    xpaths_to_try = [
        "//android.widget.RelativeLayout[@content-desc='Share']",
        "//android.widget.Button[@content-desc='Share']",
        "//android.widget.ImageButton[@content-desc='Share']",
        "//android.widget.ImageButton[@content-desc='Partager']",
        "//*[@content-desc='Share']",
        "//*[@content-desc='Partager']",
        "//*[@text='Share']",
        "//*[@text='Partager']",
        "//*[@resource-id='com.sec.android.gallery3d:id/share']",
    ]

    last_error = None

    for xp in xpaths_to_try:
        tried_xpaths.append(xp)
        try:
            el = driver.find_element(AppiumBy.XPATH, xp)
            el.click()
            time.sleep(0.8)
            log(f"Share button clicked with XPath: {xp}")
            return True
        except Exception as e:
            last_error = e
            log(f"[WARN] Share introuvable avec XPath: {xp!r}")

    log("[ERROR] Share button not found in Gallery with any known XPath.")
    log(f"[DEBUG] XPaths testés pour Share: {tried_xpaths}")
    if last_error is not None:
        traceback.print_exc()
    return False




# ------------------------------------------------------------------ #
# FLOWS WHATSAPP BUSINESS
# ------------------------------------------------------------------ #
def choose_whatsapp_business_if_needed(driver, profile_name: str | None = None) -> None:
    """
    Sélectionne l'entrée 'WhatsApp Business' dans la feuille de partage Android.

    ❗ Version simplifiée :
    - on ignore complètement locators.json & Share_Ico.txt
    - on utilise uniquement un XPath générique sur le texte "WhatsApp"
    """
    log("Sélection de WhatsApp Business (mode générique).")

    xpath = "//*[contains(@text,'WhatsApp')]"

    for attempt in range(1, 4):  # 3 petites tentatives max
        try:
            el = driver.find_element(AppiumBy.XPATH, xpath)
            el.click()
            time.sleep(0.8)
            log(f"WhatsApp Business sélectionné (generic:text_contains(WhatsApp), attempt={attempt}).")
            return
        except Exception:
            log(f"[WARN] Impossible de trouver WhatsApp Business (generic, attempt={attempt}).")
            time.sleep(0.6)

    log("❌ Impossible de sélectionner WhatsApp Business avec le XPath générique.")



def share_to_my_status(driver) -> None:
    """Sélectionne 'My status' / 'Mon statut' puis clique sur Envoyer."""
    my_status = ("//*[@resource-id='com.whatsapp.w4b:id/contactpicker_row_name' and "
                 "(contains(@text,'My status') or contains(@text,'Mon statut'))]")

    # Choix du statut
    for _ in range(5):
        try:
            driver.find_element(AppiumBy.XPATH, my_status).click()
            time.sleep(0.6)
            break
        except Exception:
            time.sleep(0.4)

    # Bouton envoyer
    send_xpath = ("//*[@content-desc='Send' or @resource-id='com.whatsapp.w4b:id/send' "
                  "or @text='Send' or contains(@content-desc,'Envoyer') or @text='Envoyer']")

    for _ in range(5):
        try:
            driver.find_element(AppiumBy.XPATH, send_xpath).click()
            time.sleep(1.0)
            break
        except Exception:
            time.sleep(0.4)

    # Sécurité : reclique au cas où
    for _ in range(3):
        try:
            driver.find_element(AppiumBy.XPATH, send_xpath).click()
            time.sleep(0.8)
        except Exception:
            break


def beep_error():
    try:
        winsound.Beep(1200, 300)
        winsound.Beep(900, 200)
    except:
        pass


def debug_dump_thumbnails(driver):
    log("=== 🔍 DEBUG THUMBNAILS DUMP ===")

    nodes = driver.find_elements(AppiumBy.XPATH, "//android.widget.FrameLayout")
    log(f"Nombre de FrameLayout trouvés : {len(nodes)}")

    idx = 0
    candidates = []

    for el in nodes:
        try:
            rid = el.get_attribute("resource-id")
            desc = el.get_attribute("content-desc")
            bounds = el.get_attribute("bounds")

            log(f"[{idx}] id={rid} desc={desc} bounds={bounds}")

            if rid and "thumbnail" in rid.lower():
                candidates.append((idx, rid, bounds))

        except:
            pass

        idx += 1

    log("=== 🔍 CANDIDATES ===")
    for (i, rid, b) in candidates:
        log(f"[Candidate] index={i}  id={rid}  bounds={b}")

    if not candidates:
        log("❌ Aucune vignette trouvée automatiquement !")
        beep_error()
    else:
        log("✔ Vignettes détectées automatiquement.")