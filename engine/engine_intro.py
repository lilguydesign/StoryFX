# -*- coding: utf-8 -*-
"""
Engine INTRO
------------
- Ouvre la galerie
- Va dans l’onglet Albums
- Ouvre l’album demandé
- Sélectionne la première vidéo
- Partage selon la plateforme (WhatsApp géré pour l’instant)
"""
import time   # 👈 AJOUTER ÇA
from .platforms import pre_platform_setup, share_to_platform
from .core import (
    log,
    ensure_adb_connected,
    make_driver,
    open_album,
    select_first_video_then_share,
    choose_whatsapp_business_if_needed,
    share_to_my_status,
    reset_gallery_home,
    unlock_screen_if_needed,
    start_gallery,  # ⬅️ ajouter ceci

)


def run(
    profile: dict,
    album: str,
    platform: str = "WhatsApp",
    platform_opts: dict | None = None,
) -> int:
    """
    profile : dict provenant de profiles.json, avec une clé supplémentaire
              'profile_name' ajoutée par runner.py
    album   : nom exact de l’album dans la Galerie
    """
    platform_opts = platform_opts or {}

    # Ajouté par runner.py : profile["profile_name"] = args.profile
    profile_name = profile.get("profile_name")

    device_id = profile.get("device_id")
    profile_label = profile.get("profile_name", "?")
    log(f"[intro] Profil : {profile_label} | device_id={device_id}")

    plat_ver = profile.get("platform_version")

    if not device_id:
        log("Profil sans device_id, abort.")
        return 1

    if not ensure_adb_connected(device_id):
        return 1

    driver = None
    try:
        # driver = make_driver(device_id, plat_ver)
        driver = make_driver(device_id, plat_ver, profile=profile)

        unlock_screen_if_needed(driver)

        # Préparation spécifique à la plateforme (ex : sélectionner la page Facebook)
        pre_platform_setup(driver, platform, platform_opts)

        # Toujours repartir d'une Galerie propre sur l'onglet Albums
        if not reset_gallery_home(driver):
            log("Impossible de revenir sur la vue Albums.")
            return 1

        if not open_album(driver, album):
            log(f"Album '{album}' introuvable.")
            return 1

        if not select_first_video_then_share(driver):
            log("Impossible de sélectionner la première vidéo.")
            # On lève une exception pour que run_with_retries puisse relancer
            raise RuntimeError("select_first_video_then_share() returned False")

        # 🚀 ICI : on est sur la feuille de partage Android (Share sheet)

        if platform == "WhatsApp":
            choose_whatsapp_business_if_needed(driver, profile_name)
            share_to_my_status(driver)
            log("Partage WhatsApp terminé.")
        else:
            share_to_platform(driver, platform, platform_opts)
            log(f"Partage {platform} terminé.")

        # 🕒 Laisser 2–3 s pour que l'upload démarre
        try:
            log("Attente 2 s, puis retour sur la Galerie...")
            time.sleep(2.0)          # tu peux mettre 3.0 si tu veux plus
            start_gallery(driver)    # ⬅️ ouvre juste l'appli Galerie au premier plan
        except Exception:
            log("[WARN] Impossible de ramener la Galerie au premier plan (INTRO).")

        return 0

        # if platform == "WhatsApp":
        #     # Icône WhatsApp Business dans la feuille de partage
        #     choose_whatsapp_business_if_needed(driver, profile_name)
        #     # Puis "My status" / "Mon statut" + bouton Envoyer
        #     share_to_my_status(driver)
        #     log("Partage WhatsApp terminé.")
        # else:
        #     # Facebook / Instagram / TikTok
        #     share_to_platform(driver, platform, platform_opts)
        #     log(f"Partage {platform} terminé.")
        #
        # # ✅ Très important : code de succès
        # return 0
        #

    finally:
        if driver is not None:
            try:
                # 🔥 Forcer Android à rester sur Galerie
                driver.activate_app("com.sec.android.gallery3d")
                time.sleep(1.0)
            except Exception:
                pass

            try:
                # ⚠️ Petit hack : envoyer HOME mais en laissant Galerie ouverte
                driver.press_keycode(3)  # HOME
                time.sleep(0.8)
            except Exception:
                pass

            try:
                driver.quit()
            except Exception:
                pass

    #
    # finally:
    #     if driver is not None:
    #         try:
    #             driver.quit()
    #         except Exception:
    #             pass
