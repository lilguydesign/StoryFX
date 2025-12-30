# StoryFx/engine/platforms.py
# -*- coding: utf-8 -*-
"""
Gestion centralisée des plateformes de publication :
- Facebook (CM / CI + page_name)
- Instagram (variant S20/S23 éventuel)
- TikTok
- WhatsApp
"""

import time
from pathlib import Path
from appium.webdriver.common.appiumby import AppiumBy
from .core import log, choose_whatsapp_business_if_needed
from selenium.common.exceptions import WebDriverException
import traceback

# ---------- Petits helpers ----------
def _findall(driver, xp): return driver.find_elements(AppiumBy.XPATH, xp)

def _click(driver, xp, delay=0.8):
    els = _findall(driver, xp)
    if els:
        els[0].click()
        time.sleep(delay)
        return True
    return False

def _maybe_click(
    driver,
    selectors: list[str],
    delay: float = 0.5,
    strategy: str = "xpath",
) -> bool:
    """
    Essaie de cliquer sur le premier élément trouvable parmi 'selectors'.

    strategy:
      - "xpath"       → selectors sont des XPATH (AppiumBy.XPATH)
      - "uiautomator" → selectors sont des UiSelector(...) (AppiumBy.ANDROID_UIAUTOMATOR)
    """
    if strategy == "uiautomator":
        by = AppiumBy.ANDROID_UIAUTOMATOR
    else:
        by = AppiumBy.XPATH

    for sel in selectors:
        try:
            el = driver.find_element(by, sel)
            el.click()
            time.sleep(delay)
            return True
        except Exception:
            continue
    return False


# ===================== FACEBOOK =====================
def _reset_facebook(driver):
    """
    Termine proprement les apps Facebook avant la pré-sélection de page.
    Équivalent minimal de reset_gallery_home mais ciblé sur Facebook.
    """
    fb_packages = [
        "com.facebook.katana",  # app principale
        "com.facebook.orca",    # Messenger
        "com.facebook.lite",    # au cas où un Lite traîne
    ]
    for pkg in fb_packages:
        try:
            driver.terminate_app(pkg)
            log(f"[FB] App terminée (reset): {pkg}")
        except Exception:
            # si l'app n'est pas installée ou déjà fermée, on ignore
            pass

def fb_preselect_page(driver, page_code: str | None, page_name: str | None):
    """
    Ouvre Facebook, sélectionne la page cible puis revient HOME.
    """

    log(f"[FB] fb_preselect_page() START (page_name={page_name!r}, page_code={page_code!r})")
    try:
        cur_pkg = getattr(driver, "current_package", None)
        log(f"[FB] current_package au début: {cur_pkg}")
    except Exception as e:
        log(f"[FB] Impossible de lire current_package au début: {e!r}")

    # 🔥 0) RESET FACEBOOK AVANT DE LA LANCER
    _reset_facebook(driver)

    # 1) Lancer / ramener Facebook devant
    launched = False

    try:
        log("[FB] Tentative activate_app('com.facebook.katana')...")
        driver.activate_app("com.facebook.katana")
        time.sleep(2.0)
        log(f"[FB] current_package après activate_app: {driver.current_package}")
        launched = True
    except Exception as e:
        log(f"[FB] activate_app a échoué: {e!r}")
        traceback.print_exc()

    if not launched:
        try:
            log("[FB] Tentative start_activity(com.facebook.katana, LoginActivity)...")
            driver.start_activity("com.facebook.katana", "com.facebook.katana.LoginActivity")
            time.sleep(2.0)
            log(f"[FB] current_package après start_activity: {driver.current_package}")
            launched = True
        except Exception as e2:
            log(f"[FB] start_activity a échoué: {e2!r}")
            traceback.print_exc()

    if not launched:
        log("[FB] ❌ Impossible de lancer Facebook via activate_app/start_activity. Abandon pré-sélection page.")
        return

    log("[FB] Facebook lancé, ouverture du menu (dernier onglet)...")

    # 2) Ouvrir le menu (icône tout à droite, quel que soit le nombre d'onglets)
    for attempt in range(8):
        try:
            menu_tabs = driver.find_elements(
                AppiumBy.XPATH,
                "//android.view.View[starts-with(@content-desc,'Menu, tab ') "
                "and contains(@content-desc,' of ')]"
            )

            if menu_tabs:
                # Dernier onglet : Menu, tab 5/5, 6/6, 7/7, ...
                menu_tabs[-1].click()
                time.sleep(1.0)
                log(f"[FB] Menu ouvert via liste des onglets (attempt={attempt+1}).")
                break

            # Fallback explicites si jamais la liste est vide
            fallback_xpaths = [
                "//android.view.View[@content-desc='Menu, tab 6 of 6']",
                "//android.view.View[@content-desc='Menu, tab 5 of 5']",
                "//android.view.View[@content-desc='Menu, tab 7 of 7']",
                "//android.view.View[@content-desc='Menu, tab 8 of 8']",
            ]
            clicked = False
            for xp in fallback_xpaths:
                try:
                    driver.find_element(AppiumBy.XPATH, xp).click()
                    time.sleep(1.0)
                    log(f"[FB] Menu ouvert via fallback XPath {xp} (attempt={attempt+1}).")
                    clicked = True
                    break
                except Exception:
                    continue

            if clicked:
                break

            raise Exception("Menu tab not found")

        except WebDriverException as e:
            # Cas typique UiAutomator2 crash : instrumentation pas démarrée
            log(f"[FB] WebDriverException lors de la recherche du menu (attempt={attempt+1}): {e!r}")
            if attempt >= 2:
                log("[FB] ❌ Problème UiAutomator2 persistant lors de l'ouverture du menu. Abandon fb_preselect_page.")
                traceback.print_exc()
                return
            time.sleep(1.0)
        except Exception as e:
            log(f"[FB] Échec pour ouvrir l'onglet Menu (attempt={attempt+1}): {e!r}")
            if attempt == 7:
                log("[FB] ❌ Échec définitif pour ouvrir l'onglet Menu.")
                traceback.print_exc()
                return
            time.sleep(0.7)

    # 3) Ouvrir le profile switcher (icône en haut permettant de choisir la page)
    log("[FB] Recherche du profile switcher (Open profile switcher / 9+)...")
    opened_switcher = False
    for attempt in range(8):
        try:
            # 3a) bouton standard (avec ou sans 'you have notifications')
            if _click(driver,
                      "//android.widget.Button[contains(@content-desc,'Open profile switcher')]",
                      delay=1.0):
                log(f"[FB] Profile switcher ouvert via bouton (attempt={attempt+1}).")
                opened_switcher = True
                break

            # 3b) fallback : le ViewGroup '9+'
            if _click(driver,
                      "//android.view.ViewGroup[@content-desc='9+']",
                      delay=1.0):
                log(f"[FB] Profile switcher ouvert via ViewGroup '9+' (attempt={attempt+1}).")
                opened_switcher = True
                break

            # 3c) fallback plus large : n’importe quel content-desc contenant 'profile switcher'
            if _click(driver,
                      "//*[contains(@content-desc,'profile switcher')]",
                      delay=1.0):
                log(f"[FB] Profile switcher ouvert via content-desc contenant 'profile switcher' (attempt={attempt+1}).")
                opened_switcher = True
                break

        except WebDriverException as e:
            log(f"[FB] WebDriverException lors de l'ouverture du profile switcher (attempt={attempt+1}): {e!r}")
        except Exception as e:
            log(f"[FB] Erreur lors de l'ouverture du profile switcher (attempt={attempt+1}): {e!r}")

        time.sleep(0.7)

    if not opened_switcher:
        log("[FB] ❌ Impossible d’ouvrir le profile switcher (flèche / 9+).")
        return

    # 4) Sélection de la page dans la liste
    clicked = False

    # 4a) priorité au page_name saisi dans l’UI
    if page_name:
        log(f"[FB] Sélection de la page par page_name='{page_name}'...")
        xpaths = [
            f"//android.view.View[@text='{page_name}']",
            f"//android.view.View[contains(@text,'{page_name}')]",
            f"//*[@text='{page_name}']",
        ]
        for xp in xpaths:
            try:
                driver.find_element(AppiumBy.XPATH, xp).click()
                # ✅ Laisser le temps à Facebook de basculer sur la page
                time.sleep(2.0)
                log(f"[FB] Page sélectionnée avec XPath: {xp}")
                clicked = True
                break
            except Exception as e:
                log(f"[FB] XPath '{xp}' KO pour page_name (err={e!r})")


    # 4b) fallback par code CM / CI
    if not clicked:
        log(f"[FB] Sélection de la page via page_code='{page_code}'...")
        if page_code == "CM":
            # Page Cameroun
            xpaths = [
                "//android.view.View[@text='Jerry Kamgang']",
                "//*[contains(@text,'Jerry Kamgang')]",
            ]
        elif page_code == "CI":
            # Page Côte d'Ivoire
            xpaths = [
                "//android.view.View[@text=\"Jerry Kamgang Côte d'Ivoire\"]",
                "//*[contains(@text,\"Jerry Kamgang Côte d'Ivoire\")]",
            ]
        else:
            xpaths = []

        for xp in xpaths:
            try:
                driver.find_element(AppiumBy.XPATH, xp).click()
                # ✅ Laisser 2s pour que Facebook charge bien la page
                time.sleep(2.0)
                log(f"[FB] Page sélectionnée avec XPath (code={page_code}): {xp}")
                clicked = True
                break
            except Exception as e:
                log(f"[FB] XPath '{xp}' KO pour code {page_code} (err={e!r})")

    if not clicked:
        log("[FB] ❌ Impossible de sélectionner la page Facebook.")
        return

    # 5) Retour HOME
    log("[FB] ✅ Page Facebook sélectionnée. Retour HOME avant Galerie...")
    try:
        # ✅ Petite pause pour laisser le temps à l’UI de se stabiliser sur la page
        time.sleep(1.0)
        driver.press_keycode(3)  # HOME
        time.sleep(0.8)
        log(f"[FB] current_package après HOME: {driver.current_package}")
    except Exception as e:
        log(f"[FB] Problème lors du retour HOME: {e!r}")
        traceback.print_exc()


def share_to_facebook(driver, platform_opts: dict | None = None) -> None:
    """
    Sélectionne l’icône 'Facebook' dans la feuille de partage,
    puis clique sur le bouton Share/Partager dans Facebook.
    """
    log("[FB] Sélection de l’icône Facebook dans la feuille de partage...")
    platform_opts = platform_opts or {}

    # 1) Essais robustes sur le texte pour l’icône Facebook
    clicked = _maybe_click(driver, [
        # XPath principal (Appium Inspector)
        "//android.widget.TextView[@resource-id='android:id/text1' and @text='Facebook']",

        # Variantes texte + content-desc
        "//android.widget.TextView[contains(@text,'Facebook')]",
        "//*[@text='Facebook']",
        "//*[@text='Facebook Your Story']",
        "//*[@content-desc='Facebook']",
        "//*[contains(@content-desc,'Facebook')]",
    ], delay=1.0)

    # 2) Fallback : ton Share_Ico.txt historique
    if not clicked:
        try:
            ico_path = Path(__file__).resolve().parent.parent / "Share_Ico.txt"
            xp = ico_path.read_text(encoding="utf-8").strip().replace('"', "'")
            if xp:
                if _maybe_click(driver, [xp], delay=1.0):
                    log("✔ Icône Facebook tapée via Share_Ico.txt.")
                    clicked = True
        except Exception as e:
            log(f"[FB][WARN] Impossible de lire Share_Ico.txt : {e}")

    if not clicked:
        log("❌ Impossible de taper sur l’icône Facebook dans la feuille de partage.")
        return

    log("[FB] Icône Facebook sélectionnée, attente que l’éditeur charge...")

    # 🔥 Laisser le temps à Facebook de charger l’écran de partage
    # (surtout pour les VIDÉOS : on allonge volontairement)
    time.sleep(3.0)

    log("[FB] Icône Facebook sélectionnée, recherche du bouton Share/Partager...")

    # 3) Bouton Share dans Facebook (toutes les possibilités connues)
    clicked_share = _maybe_click(driver, [
        # A) Bouton avec content-desc "Share" (prise en compte de ta capture)
        "//android.widget.Button[@content-desc='Share']",

        # B) TextView 'Share' avec resource-id Facebook (id masqué dans Inspector)
        #    → on matche par starts-with sur le prefix com.facebook.katana:id/
        "//android.widget.TextView[starts-with(@resource-id,'com.facebook.katana:id/') and @text='Share']",

        # C) Variantes texte simples
        "//*[@text='Share']",
        "//*[@text='Partager']",
        "//*[contains(@text,'Share')]",
        "//*[contains(@text,'Partager')]",

        # D) Variantes content-desc
        "//*[@content-desc='Share']",
        "//*[@content-desc='Partager']",
        "//*[contains(@content-desc,'Share')]",
        "//*[contains(@content-desc,'Partager')]",
    ], delay=3.0)  # ⬅️ délai TRIPLÉ pour laisser le temps aux vidéos

    if clicked_share:
        log("✅ Bouton Share Facebook cliqué (story/post envoyée).")
    else:
        log("[FB] ⚠️ Bouton Share/Partager introuvable après chargement Facebook.")


# ===================== INSTAGRAM =====================
def share_to_instagram(driver, mode="auto"):

    """
    Flow Instagram Story générique.

    mode:
      - "intro" : une seule vidéo / image (intro)
      - "multi" : plusieurs images/vidéos (album)
      - "auto"  : tente d'abord le comportement intro, puis bascule en multi si besoin
    """
    mode = (mode or "auto").lower()
    is_intro = mode == "intro"
    is_multi = mode == "multi"

    # Facteur de délai spécial Instagram (surtout utile pour les vidéos lourdes)
    IG_FACTOR = 4.0

    # Petit helper pour factoriser Share + Done
    def _ig_share_and_done(from_multi: bool):
        # 4) Bouton 'Share'
        log("[IG] Recherche du bouton 'Share' dans la feuille 'Share'...")
        clicked_share = _maybe_click(driver, [
            "(//android.widget.TextView[@text='Share'])[2]",
            "//*[@text='Share']",
        ], delay=1.0 * IG_FACTOR)
        if not clicked_share:
            log("[IG] ⚠️ Bouton 'Share' introuvable, abandon.")
            return False

        # 5) Bouton 'Done'
        log("[IG] Recherche du bouton 'Done' dans 'Also share to'...")
        clicked_done = _maybe_click(driver, [
            "//android.widget.TextView[@text='Done']",
            "//*[@text='Done']",
        ], delay=1.0 * IG_FACTOR)

        if clicked_done:
            if from_multi:
                log("✅ Story publiée sur Instagram (Next → Share → Done, mode multi).")
            else:
                log("✅ Story publiée sur Instagram via 'Share to' → Share → Done (sans Next).")
            return True
        else:
            log("[IG] ⚠️ Bouton 'Done' introuvable : publication Instagram non confirmée.")
            return False

    # 1) Feuille de partage Android → entrée Instagram (si visible)
    log("[IG] Sélection d'Instagram dans la feuille de partage (si visible)...")
    if not _maybe_click(driver, [
        "//*[@text='Instagram' or contains(@content-desc,'Instagram')]"
    ], delay=1.2 * IG_FACTOR):
        log("[IG] Instagram introuvable dans la feuille de partage (on est peut-être déjà dans l'app).")

    # 2) ESSAI RAPIDE (INTRO / AUTO) : Your story / Your stories / Share to
    if not is_multi:
        # 2a) Your story / Votre story / Your stories
        log("[IG] Tentative clic sur 'Your story' / 'Votre story' / 'Your stories'...")
        clicked_story = _maybe_click(driver, [
            "//*[@text='Your story']",
            "//*[@text='Votre story']",
            "//*[contains(@content-desc,'Your story')]",
            "//*[contains(@content-desc,'Votre story')]",
            "//android.widget.Button[@content-desc='Your stories']",
        ], delay=1.0 * IG_FACTOR)

        if clicked_story:
            # Dans ce cas, la story est postée directement, on ne fait PAS Next/Share/Done
            log("✅ Story publiée sur Instagram via 'Your story / Your stories' (mode intro).")
            return
        else:
            log("[IG] 'Your story' / 'Your stories' introuvable.")

        # 2b) Bouton "Share to" (cas intro avec partage vers story)
        log("[IG] Tentative clic sur 'Share to'...")
        clicked_share_to = _maybe_click(driver, [
            "//android.widget.Button[@content-desc='Share to']/android.widget.TextView",
        ], delay=1.0 * IG_FACTOR)

        if clicked_share_to:
            log("[IG] 'Share to' cliqué, enchaînement Share → Done (sans Next).")
            _ig_share_and_done(from_multi=False)
            return

    # Si on est en mode INTRO explicite et qu'on n'a ni Story ni Share to,
    # on NE DOIT PAS lancer le flow multi.
    if is_intro:
        log("[IG] Mode intro : pas de flow multi (Next → Share → Done). Abandon.")
        return

    # 3) FLOW AVANCÉ (MULTI ou AUTO) → Next → Share → Done
    #    - utilisé pour mode "multi"
    #    - ou pour mode "auto" si on n’a pas trouvé Story / Share to
    log("[IG] Flow multi Instagram (Next → Share → Done)...")

    # 🔥 On laisse le temps à Instagram de charger toutes les vignettes,
    # surtout quand il y a plusieurs vidéos (sinon 'Next' arrive trop tard).
    log("[IG] Pause avant recherche du bouton 'Next' (chargement vidéos)...")
    time.sleep(1.0 * IG_FACTOR)

    log("[IG] Recherche du bouton 'Next'...")
    clicked_next = _maybe_click(driver, [
        # bouton 'Next' (content-desc)
        "//android.widget.Button[@content-desc='Next']",

        # bouton 'Next' dans le tray (texte + resource-id spécifiques)
        "//android.widget.TextView[@resource-id='com.instagram.android:id/media_thumbnail_tray_button_text' and @text='Next']",
        "//android.widget.TextView[@resource-id='com.instagram.android:id/media_thumbnail_tray_button_text']",

        # layout qui contient le bouton Next (au cas où on clique le container)
        "//android.widget.LinearLayout[@resource-id='com.instagram.android:id/media_thumbnail_tray_next_buttons_layout']",

        # fallback texte simple
        "//*[@text='Next']",
    ], delay=1.0 * IG_FACTOR)

    if not clicked_next:
        log("[IG] ⚠️ Bouton 'Next' introuvable, abandon du flow multi.")
        return

    # 4 + 5) Share → Done (mode multi)
    _ig_share_and_done(from_multi=True)


# ===================== WHATSAPP =====================
def share_to_whatsapp_status(driver):
    """On garde tes helpers W4B (sélecteur My status ensuite dans l’engine)."""
    choose_whatsapp_business_if_needed(driver)
    log("✅ Feuille WhatsApp Business ouverte.")

# ===================== TIKTOK =====================
def share_to_tiktok(driver):
    """
    Feuille de partage → TikTok → premier bouton (Photo/story)
    → mute éventuel → publier en story.
    """

    # facteur global pour TikTok (délais un peu plus longs)
    TT_FACTOR = 2.0

    # 1) Feuille de partage Android → entrée TikTok
    log("[TT] Sélection de TikTok dans la feuille de partage...")
    if not _maybe_click(driver, [
        "//*[@text='TikTok' or contains(@content-desc,'TikTok')]",
    ], delay=1.2 * TT_FACTOR):
        log("[TT] ⚠️ TikTok introuvable dans la feuille de partage.")
        return

    # 2) Premier bouton dans TikTok (Photo / première vignette)
    log("[TT] Sélection du premier bouton (Photo / Vidéo / première image)...")
    clicked_first = _maybe_click(
        driver,
        [
            # d’abord les boutons texte (plus stables)
            "//android.widget.Button[@resource-id='com.zhiliaoapp.musically:id/ktc' and @text='Photo']",
            "//android.widget.Button[@resource-id='com.zhiliaoapp.musically:id/ktc' and @text='Video']",

            # en DERNIER recours seulement : la 1re image ktq (fragile si l’ordre change)
            "(//android.widget.ImageView[@resource-id='com.zhiliaoapp.musically:id/ktq'])[1]",
        ],
        delay=2.5 * TT_FACTOR,
    )

    if not clicked_first:
        log("[TT] ⚠️ Impossible de cliquer sur le premier bouton (Photo / ktq).")
        # On continue quand même, au cas où l'écran suivant est déjà affiché

    # 3) Désactiver le son (mute) pour publier en story
    log("[TT] Tentative de désactivation du son (mute)...")
    _maybe_click(
        driver,
        [
            "//android.widget.ImageView[@resource-id='com.zhiliaoapp.musically:id/c8b']",
            "//android.view.View[@resource-id='com.zhiliaoapp.musically:id/c8f']",
        ],
        delay=0.8 * TT_FACTOR,
    )

    # petite pause pour laisser TikTok préparer l'écran "Your Story"
    time.sleep(1.0 * TT_FACTOR)

    # 4) Bouton de publication en story ("Your Story" / "Story")
    log("[TT] Recherche du bouton de publication (story / post)...")
    clicked_publish = _maybe_click(
        driver,
        [
            # A) XPATH basé sur le texte "Your Story" / "Story"
            "//android.widget.TextView[@resource-id='com.zhiliaoapp.musically:id/s30' and (@text='Your Story' or @text='Story')]",
            "//android.widget.TextView[contains(@text,'Your Story') or contains(@text,'Story')]",

            # B) Layout complet du bouton de story (container)
            "//android.widget.FrameLayout[@resource-id='com.zhiliaoapp.musically:id/mnh']/android.widget.LinearLayout",
            "//android.widget.FrameLayout[@resource-id='com.zhiliaoapp.musically:id/mnh']",

            # C) Autres vues associées au bouton "Your Story"
            "//android.view.View[@resource-id='com.zhiliaoapp.musically:id/app']",
            "//android.widget.FrameLayout[@resource-id='com.zhiliaoapp.musically:id/mni']",
            "//android.widget.ImageView[@resource-id='com.zhiliaoapp.musically:id/hlr']",
        ],
        delay=1.5 * TT_FACTOR,
    )

    # D) Dernière chance : UiSelector sur le texte
    if not clicked_publish:
        clicked_publish = _maybe_click(
            driver,
            [
                'new UiSelector().text("Your Story")',
                'new UiSelector().textContains("Story")',
                'new UiSelector().descriptionContains("Your Story")',
                'new UiSelector().descriptionContains("Story")',
            ],
            delay=1.5 * TT_FACTOR,
            strategy="uiautomator",
        )

    if clicked_publish:
        log("✅ Vidéo postée en story TikTok.")
    else:
        log("[TT] ⚠️ Bouton de publication TikTok introuvable : story non confirmée.")


# ===================== ROUTAGE (hooks) =====================
def pre_platform_setup(driver, platform: str, options: dict | None):
    """
    Hook AVANT d’entrer dans la Galerie (utile pour Facebook : switch de page).
    options possibles :
      - page ('CM' / 'CI')
      - page_name (nom libre saisi en UI, prioritaire)
    """
    if platform == "Facebook":
        page_code = (options or {}).get("page")
        page_name = (options or {}).get("page_name")  # vient du front
        if page_code or page_name:
            fb_preselect_page(driver, page_code, page_name)

def share_to_platform(driver, platform: str, options: dict | None = None) -> None:
    """
    Action APRÈS avoir tapé 'Share' dans la Galerie.
    """
    options = options or {}
    platform = (platform or "").strip()

    if platform == "WhatsApp":
        # On se contente d’ouvrir la feuille WAB, le reste est fait dans engine_intro
        share_to_whatsapp_status(driver)
        return

    if platform == "Facebook":
        share_to_facebook(driver, options)
        return

    if platform == "Instagram":
        # Plus de variante IG : un seul Instagram par téléphone
        share_to_instagram(driver)
        return


    if platform == "TikTok":
        share_to_tiktok(driver)
        return

    log(f"[WARN] Plateforme inconnue pour share_to_platform : {platform}")
