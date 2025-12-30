# -*- coding: utf-8 -*-
import PySimpleGUI as sg

from ui.ui_paths_helpers import load_profiles_dict


def build_locators_tab():
    """
    Onglet Admin - Locators (XPaths).

    - Plateforme : WhatsApp, Facebook, Instagram, TikTok
    - Profil/device : default + tous les profils de profiles.json
    - Clé : type de locator (share_entry, my_status, send_button)
    - Champ Multiline pour saisir l'XPath
    - Boutons Charger / Enregistrer (gérés dans app.py)
    """
    profiles = load_profiles_dict()
    profile_names = ["default"] + sorted(profiles.keys())

    # On garde uniquement les 3 étapes réelles de ton flow :
    # 1) share_entry  : icône / texte de l'app dans la feuille de partage (WhatsApp Business, Facebook, IG, TikTok)
    # 2) my_status    : entrée "My status" dans WhatsApp
    # 3) send_button  : bouton Send / Envoyer dans WhatsApp
    locator_keys = [
        "share_entry",   # entrée générique de partage (WhatsApp Business, Facebook, IG, TikTok)
        "my_status",     # entrée "My status" dans WhatsApp
        "send_button",   # bouton Send / Envoyer
    ]

    layout = [
        [
            sg.Text("Plateforme"),
            sg.Combo(
                ["WhatsApp", "Facebook", "Instagram", "TikTok"],
                key="-LOC_PLATFORM-",
                readonly=True,
                size=(15, 1),
            ),
        ],
        [
            sg.Text("Profil / device"),
            sg.Combo(
                profile_names,
                key="-LOC_PROFILE-",
                readonly=True,
                size=(20, 1),
            ),
        ],
        [
            sg.Text("Clé"),
            sg.Combo(
                locator_keys,
                key="-LOC_KEY-",
                readonly=True,
                size=(18, 1),
            ),
        ],
        [
            sg.Multiline(
                "",
                size=(80, 6),
                key="-LOC_XPATH-",
                autoscroll=True,
            )
        ],
        [
            sg.Button("Charger", key="-LOC_LOAD-"),
            sg.Button("Enregistrer", key="-LOC_SAVE-"),
        ],
    ]

    return layout
