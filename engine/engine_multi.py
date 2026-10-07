# -*- coding: utf-8 -*-
"""
Multi-selection engine (codes 3,4,5,6,7 …)
"""


import time
import math

from ui.ui_paths_helpers import load_albums_dict

from .platforms import pre_platform_setup, share_to_platform
from .gallery_batch import BatchSelectionError, select_exact_batch, verify_shared_batch

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
      - vérifie la sélection réelle de `count` images avant le partage
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
      8 : quantité reçue par le partage Android non confirmée
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
    except (TypeError, ValueError):
        log("[multi] Quantité invalide : aucune publication.")
        return 1
    if not 1 <= count <= 30:
        log("[multi] Quantité hors limite : aucune publication.")
        return 1

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

        # Verify the UI count, including a first thumbnail still selected after long press.
        try:
            selected = select_exact_batch(driver, count, album_total=get_album_size(album_name),
                                          scroll_max=compute_scroll_max_for_album(album_name))
        except BatchSelectionError:
            log("[multi] Lot exact non confirmé : aucun partage autorisé.")
            return 6
        log(f"[multi] Sélection réelle confirmée : {selected}/{count}.")

        # Bouton Share
        if not tap_share_button(driver):
            return 7

        # Refuse a provider handoff if Android received fewer images than configured.
        try:
            verify_shared_batch(driver, count)
        except BatchSelectionError:
            log("[multi] Quantité reçue par Android non confirmée : publication arrêtée.")
            return 8

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


    finally:
        try:
            driver.quit()
        except Exception:
            pass
