# -*- coding: utf-8 -*-
"""
Multi-selection engine (codes 3,4,5,6,7 …)
"""

from appium.webdriver.common.touch_action import TouchAction

import time
import random
import math
from pathlib import Path

from ui.ui_paths_helpers import load_albums_dict
from appium.webdriver.common.appiumby import AppiumBy

from .platforms import pre_platform_setup, share_to_platform

from .core import (
    log,
    ensure_adb_connected,
    make_driver,
    open_album,
    long_press_first_thumb,
    tap_share_button,
    choose_whatsapp_business_if_needed,
    share_to_my_status,
    reset_gallery_home,
    unlock_screen_if_needed,
    start_gallery,  # ⬅️ ajouter ceci
    debug_dump_thumbnails,  # ✅ AJOUTER CETTE LIGNE
)

ALBUMS_CACHE = None


def get_album_size(album_name: str) -> int:
    """Retourne album_size pour un album donné en lisant albums.json."""
    global ALBUMS_CACHE
    if ALBUMS_CACHE is None:
        ALBUMS_CACHE = load_albums_dict()
    cfg = ALBUMS_CACHE.get(album_name)
    return int(cfg.get("album_size", 0) or 0) if cfg else 0


def compute_scroll_max_for_album(album_name: str) -> int:
    """
    Calcule scroll_max en fonction de albums.json.
    Formule : ceil(n / 200), bornée entre 1 et 10.
    """
    n = get_album_size(album_name)
    if not n:
        return 3
    scroll_max = math.ceil(n / 250.0)
    if scroll_max < 1:
        return 1
    if scroll_max > 10:
        return 10
    return scroll_max


def run(
    profile: dict,
    album_name: str,
    count: int,
    platform: str = "WhatsApp",
    platform_opts: dict | None = None,
) -> int:
    """
    Engine MULTI :
      - remet la Galerie dans un état propre (reset_gallery_home)
      - ouvre l’album demandé
      - active la sélection multiple (long press)
      - sélectionne `count` images : 1 par "page", puis scroll
      - partage vers la plateforme choisie :
          * WhatsApp Business (My status) si platform == "WhatsApp"
          * sinon Facebook / Instagram / TikTok via share_to_platform()

    Codes retour :
      1 : ADB non connecté ou profil sans device_id
      2 : impossible de remettre la Galerie propre (reset_gallery_home)
      4 : album introuvable
      5 : impossible de faire le long press sur la première vignette
      6 : pas assez d’images sélectionnées
      7 : bouton Share introuvable
      0 : succès
    """
    platform_opts = platform_opts or {}

    device_id = profile.get("device_id")
    plat_ver  = profile.get("platform_version")
    profile_name = profile.get("profile_name")  # éventuellement utile plus tard

    if not device_id:
        log("[multi] Profil sans device_id, abort.")
        return 1

    if not ensure_adb_connected(device_id):
        return 1

    # S’assurer que count est bien un int
    try:
        count = int(count)
    except Exception:
        count = 11

    # driver = make_driver(device_id, plat_ver)
    driver = make_driver(device_id, plat_ver, profile=profile)

    unlock_screen_if_needed(driver)

    try:
        # Déverrouillage simple si besoin
        try:
            if driver.is_locked():
                driver.press_keycode(82)
                time.sleep(0.5)
        except Exception:
            pass

        # Préparation éventuelle (utile surtout pour Facebook)
        pre_platform_setup(driver, platform, platform_opts)

        # 🔥 Toujours repartir d'une Galerie propre sur l'onglet Albums
        if not reset_gallery_home(driver):
            log("[multi] Impossible de remettre la Galerie dans un état propre.")
            return 2

        # Ouvrir l’album
        if not open_album(driver, album_name):
            log(f"[multi] Album '{album_name}' introuvable.")
            return 4

        # Activer la multi-sélection (long press sur la première vignette)
        if not long_press_first_thumb(driver):
            log("[multi] Impossible de faire le long press sur la première vignette.")
            return 5

        # Scroll max dynamique en fonction de l'album (basé sur albums.json)
        scroll_max   = compute_scroll_max_for_album(album_name)
        album_total  = get_album_size(album_name)
        log(f"[multi] scroll_max={scroll_max} pour l'album '{album_name}' (album_size={album_total}).")

        # Par sécurité : ne jamais demander plus d'images que l'album n'en contient
        if album_total and count > album_total:
            count = album_total
            log(f"[multi] count ajusté à {count} (taille réelle de l'album).")

        # ------------------------------------------------------------------
        # MODE 1 : petits albums (≤ 32 photos) → une seule page, aucun scroll
        # ------------------------------------------------------------------
        if album_total and album_total <= 32:
            log("[multi] Mode 'small album' activé (≤ 32 photos) : aucune analyse de scroll.")

            thumbs = driver.find_elements(
                AppiumBy.XPATH,
                "(//android.widget.FrameLayout[@resource-id="
                "'com.sec.android.gallery3d:id/thumbnail_preview_layout'])",
            )

            if not thumbs:
                log("[multi] ❌ Aucune vignette trouvée sur la page unique.")
                # Debug spécial S23 pour voir ce que Samsung renvoie
                debug_dump_thumbnails(driver)
                return 6

            idxs = list(range(len(thumbs)))
            random.shuffle(idxs)

            selected = 0
            for i in idxs:
                if selected >= count:
                    break
                try:
                    thumbs[i].click()
                    selected += 1
                    log(f"[multi] Image sélectionnée (total={selected}/{count}).")
                    time.sleep(0.2)
                except Exception:
                    continue

            if selected < count:
                log(f"[multi] Seulement {selected}/{count} images sélectionnées → code 6 (small album).")
                return 6

        # ------------------------------------------------------------------
        # MODE 2 : grands albums (> 32 photos) → algo classique avec scroll
        # ------------------------------------------------------------------
        else:
            # --- Sélection multi : 1 image puis scroll, comme ton ancien script ---
            selected = 0
            empty_loops = 0
            max_empty_loops = 10

            while selected < count and empty_loops < max_empty_loops:
                thumbs = driver.find_elements(
                    AppiumBy.XPATH,
                    "(//android.widget.FrameLayout[@resource-id="
                    "'com.sec.android.gallery3d:id/thumbnail_preview_layout'])",
                )

                if not thumbs:
                    empty_loops += 1
                    log(f"[multi] Aucune vignette trouvée (loop={empty_loops}), on scroll.")

                    # 🔍 DEBUG SPÉCIAL S23 : voir ce que Samsung affiche réellement
                    if empty_loops == 1:
                        debug_dump_thumbnails(driver)

                else:
                    idxs = list(range(len(thumbs)))
                    random.shuffle(idxs)

                    clicked = False
                    for i in idxs:
                        if selected >= count:
                            break
                        try:
                            thumbs[i].click()
                            selected += 1
                            clicked = True
                            log(f"[multi] Image sélectionnée (total={selected}/{count}).")
                            time.sleep(0.2)
                            break
                        except Exception:
                            continue

                    if not clicked:
                        empty_loops += 1
                        log(
                            f"[multi] Impossible de sélectionner une image sur cette page "
                            f"(loop={empty_loops})."
                        )

                # Scroll 1 → scroll_max fois selon la taille de l'album
                size = driver.get_window_size()
                start_x = size["width"] // 2
                start_y = int(size["height"] * 0.75)
                end_y   = int(size["height"] * 0.25)

                scroll_times = random.randint(1, scroll_max)
                for _ in range(scroll_times):
                    driver.swipe(start_x, start_y, start_x, end_y, 900)
                    time.sleep(0.4)

            if selected < count:
                log(f"[multi] Seulement {selected}/{count} images sélectionnées → code 6.")
                return 6

        # Bouton Share
        if not tap_share_button(driver):
            return 7

        # ⭐ ROUTAGE SELON LA PLATEFORME ⭐
        if platform == "WhatsApp":
            choose_whatsapp_business_if_needed(driver, profile_name)
            share_to_my_status(driver)
            log("✔ Multi selection posted (WhatsApp Status).")
        else:
            share_to_platform(driver, platform, platform_opts)
            log(f"✔ Multi selection posted on {platform}.")

        # 🕒 Laisser le temps à l'upload de partir, puis revenir sur la Galerie
        try:
            log("Attente 2 s, puis retour sur la Galerie...")
            time.sleep(2.0)
            start_gallery(driver)    # ⬅️ met la Galerie au premier plan, sans fermer les autres apps
        except Exception:
            log("[WARN] Impossible de ramener la Galerie au premier plan (MULTI).")

        return 0


        # # ⭐ ROUTAGE SELON LA PLATEFORME ⭐
        # if platform == "WhatsApp":
        #     # Feuille de partage → WhatsApp Business → My status
        #     choose_whatsapp_business_if_needed(driver, profile_name)
        #     share_to_my_status(driver)
        #     log("✔ Multi selection posted (WhatsApp Status).")
        # else:
        #     # Facebook / Instagram / TikTok
        #     share_to_platform(driver, platform, platform_opts)
        #     log(f"✔ Multi selection posted on {platform}.")
        #
        # return 0

    finally:
        try:
            driver.quit()
        except Exception:
            pass
