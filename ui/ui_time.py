# ui/ui_time.py
# -*- coding: utf-8 -*-
"""
Module de gestion du temps du scheduler (UI Temps).

Ce module extrait **toute** la logique qui était auparavant dans app.py :
- Initialisation du bloc d'heure (mode auto / PC)
- Passage Auto <-> Manuel
- Lecture / écriture dans scheduler_clock.json
- Stabilisation de l’heure (pas d’écrasement pendant que l'utilisateur tape)
- Rafraîchissement automatique (toutes les secondes) uniquement en mode manuel
- Mise à jour HH/MM selon le profil sélectionné
- Suppression complète de AM/PM et du format 12h

Tout fonctionne désormais en **24h strict**, basé sur ce que tu veux.
"""

import json
from datetime import datetime
from scheduler import load_clock_state


# --------------------------------------------------------------------------
# 🔥 1) FONCTION : write_clock_state
# --------------------------------------------------------------------------
def write_clock_state(path, mode: str, hhmm: str | None = None):
    """
    Sauvegarde le mode et l'heure dans scheduler_clock.json.

    mode  : "auto" ou "manual"
    hhmm  : "HH:MM" (24h) uniquement utilisé si mode == manual

    Ce fichier est utilisé par le scheduler pour savoir s'il doit
    utiliser l'heure PC ou une heure imposée.
    """
    data = {"mode": mode}
    if mode == "manual" and hhmm:
        data["time"] = hhmm

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[UITemps] Erreur write_clock_state: {e}")


# --------------------------------------------------------------------------
# 🔥 2) FONCTION : init_time_controls (Mode AUTO)
# --------------------------------------------------------------------------
def init_time_controls(win, clock_path):
    """
    Initialise le bloc de temps en mode AUTO :
    - Heure PC réelle (24h)
    - HH et MM verrouillés
    - Radio bouton Auto sélectionné
    - write_clock_state("auto")
    """

    now = datetime.now()
    hh = f"{now.hour:02d}"
    mm = f"{now.minute:02d}"

    # Mise à jour UI
    win["-TIME_HH-"].update(hh)
    win["-TIME_MM-"].update(mm)

    win["-TIME_AUTO-"].update(True)
    win["-TIME_MANUAL-"].update(False)

    # Désactivation des champs
    win["-TIME_HH-"].update(disabled=True)
    win["-TIME_MM-"].update(disabled=True)

    # Sauvegarde état
    write_clock_state(clock_path, "auto", f"{hh}:{mm}")


# --------------------------------------------------------------------------
# 🔥 3) Récupération HH:MM depuis l’UI (mode manuel)
# --------------------------------------------------------------------------
def get_manual_hhmm(vals) -> str | None:
    """
    Récupère HH et MM depuis l'UI et retourne "HH:MM".
    Validation simple : 00–23 pour HH et 00–59 pour MM.

    Retourne None si invalide.
    """
    hh = (vals.get("-TIME_HH-") or "").strip()
    mm = (vals.get("-TIME_MM-") or "").strip()

    try:
        h = int(hh)
        m = int(mm)
    except:
        return None

    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None

    return f"{h:02d}:{m:02d}"


# --------------------------------------------------------------------------
# 🔥 4) Mise à jour automatique de l'affichage en MANUEL (toutes les 1 s)
# --------------------------------------------------------------------------
def auto_refresh_manual_time(win, editing_manual_time: bool):
    """
    Appelé toutes les ~1 seconde par app.py.
    NE rafraîchit que SI :
    - le mode est MANUEL
    - l'utilisateur n’est PAS en train de taper
    - le scheduler_clock.json contient une heure valide

    Ce comportement est identique à ton application actuelle,
    mais SANS écraser l'heure quand elle vaut "00:00" ou quand l'utilisateur écrit.
    """

    # Ne jamais toucher si l’utilisateur est en train de taper
    if editing_manual_time:
        return

    state = load_clock_state()
    hhmm = state.get("time")

    # Ne rien faire si vide ou "00:00"
    if not hhmm or hhmm == "00:00":
        return

    try:
        h, m = map(int, hhmm.split(":"))
    except:
        return

    # Mise à jour UI (24h natif)
    win["-TIME_HH-"].update(f"{h:02d}")
    win["-TIME_MM-"].update(f"{m:02d}")


# --------------------------------------------------------------------------
# 🔥 5) Réaction au changement de profil
# --------------------------------------------------------------------------
def update_time_selectors_from_profile(win, profile_name, systems, matrix_rows, profiles):
    """
    NOUVELLE LOGIQUE (demandée par Jerry) :
    - Les HEURES = toutes les heures de TOUS les systèmes.json (24h)
    - Les MINUTES = tous les offsets de TOUS les profils (triés, sans doublons)
    - Le profil ne détermine PLUS les heures ni les minutes
    """

    # ------------------------------------------------------------------
    # 1) Extraire TOUTES les heures de systems.json
    # ------------------------------------------------------------------
    all_hours = set()

    for sys_name, times in systems.items():
        for t in times:
            try:
                hh, mm = t.split(":")
                all_hours.add(hh.zfill(2))
            except:
                pass

    hours_list = sorted(all_hours, key=lambda x: int(x))

    # ------------------------------------------------------------------
    # 2) Extraire TOUS les offset_minutes des profils
    # ------------------------------------------------------------------
    all_minutes = set()

    for prof_name, cfg in profiles.items():
        try:
            off = int(cfg.get("offset_minutes", 0))
            all_minutes.add(f"{off:02d}")
        except:
            pass

    minutes_list = sorted(all_minutes, key=lambda x: int(x))

    # ------------------------------------------------------------------
    # 3) Mise à jour UI
    # ------------------------------------------------------------------
    win["-TIME_HH-"].update(values=hours_list)
    win["-TIME_MM-"].update(values=minutes_list)

    # Sélectionner par défaut la première valeur
    if hours_list:
        win["-TIME_HH-"].update(hours_list[0])
    if minutes_list:
        win["-TIME_MM-"].update(minutes_list[0])

    print(f"[UITemps] HEURES chargées = {hours_list}")
    print(f"[UITemps] MINUTES chargées = {minutes_list}")
