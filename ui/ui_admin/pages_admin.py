# ui/ui_admin/pages_admin.py
# -*- coding: utf-8 -*-

import json
from pathlib import Path
import PySimpleGUI as sg

from ui.tabs.ui_tabs_admin import refresh_pages_table, PAGES_FILE, _load_pages_from_json


# -----------------------------------------------------------
#  🔥 Rafraîchir les combos Pays / Page dans toute l'application
# -----------------------------------------------------------
def _refresh_country_page_combos(win):
    """Met à jour les combos Pays/Page dans Launcher et Matrix."""
    pages = _load_pages_from_json()
    countries = sorted({p.get("country", "") for p in pages if p.get("country")})
    names     = sorted({p.get("name", "")    for p in pages if p.get("name")})

    # Launcher
    try:
        win["-PAGE-"].update(values=countries)
        win["-PAGE_NAME-"].update(values=names)
    except Exception:
        pass

    # Matrix
    try:
        win["-M_PAGE-"].update(values=countries)
        win["-M_PNAME-"].update(values=names)
    except Exception:
        pass



# -----------------------------------------------------------
#  🔥 Sauvegarde des pages
# -----------------------------------------------------------
def _save_pages(pages):
    """Sauvegarde la liste des pages dans pages.json."""
    PAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PAGES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"pages": pages}, f, ensure_ascii=False, indent=2)



# -----------------------------------------------------------
#  🔥 Gestion des événements Pages (Add / Update / Delete)
# -----------------------------------------------------------
def handle_pages_events(ev, vals, win):
    """
    GÈRE 100% DE LA LOGIQUE PAGES :

        -PG_TABLE-
        -PG_ADD-
        -PG_UPDATE-
        -PG_DEL-
    """

    pages = _load_pages_from_json()

    # ------------------------------------------------------
    # 1) Sélection dans la table
    # ------------------------------------------------------
    if ev == "-PG_TABLE-":
        sel = vals.get("-PG_TABLE-", [])
        if sel:
            idx = sel[0]
            if 0 <= idx < len(pages):
                row = pages[idx]
                win["-PG_COUNTRY-"].update(row.get("country", ""))
                win["-PG_NAME-"].update(row.get("name", ""))
        return True


    # ------------------------------------------------------
    # 2) Ajouter
    # ------------------------------------------------------
    if ev == "-PG_ADD-":
        country = (vals.get("-PG_COUNTRY-") or "").strip()
        name    = (vals.get("-PG_NAME-") or "").strip()

        if not country or not name:
            sg.popup_error("Pays et Page sont obligatoires.")
            return True

        for p in pages:
            if p.get("country") == country and p.get("name") == name:
                sg.popup_error("Cette combinaison existe déjà.")
                return True

        pages.append({"country": country, "name": name})
        _save_pages(pages)
        refresh_pages_table(win)
        _refresh_country_page_combos(win)

        sg.popup("Page ajoutée.")
        return True



    # ------------------------------------------------------
    # 3) Mettre à jour
    # ------------------------------------------------------
    if ev == "-PG_UPDATE-":
        sel = vals.get("-PG_TABLE-", [])
        if not sel:
            sg.popup_error("Sélectionne une ligne d'abord.")
            return True

        idx = sel[0]
        if not (0 <= idx < len(pages)):
            return True

        country = (vals.get("-PG_COUNTRY-") or "").strip()
        name    = (vals.get("-PG_NAME-") or "").strip()

        if not country or not name:
            sg.popup_error("Pays et Page sont obligatoires.")
            return True

        pages[idx] = {"country": country, "name": name}
        _save_pages(pages)
        refresh_pages_table(win)
        _refresh_country_page_combos(win)

        sg.popup("Page mise à jour.")
        return True



    # ------------------------------------------------------
    # 4) Supprimer
    # ------------------------------------------------------
    if ev == "-PG_DEL-":
        sel = vals.get("-PG_TABLE-", [])
        if not sel:
            sg.popup_error("Sélectionne une ligne à supprimer.")
            return True

        idx = sel[0]
        if not (0 <= idx < len(pages)):
            return True

        row = pages[idx]
        if sg.popup_yes_no(
            f"Supprimer la page '{row.get('name')}' ({row.get('country')}) ?"
        ) != "Yes":
            return True

        del pages[idx]
        _save_pages(pages)
        refresh_pages_table(win)
        _refresh_country_page_combos(win)

        win["-PG_COUNTRY-"].update("")
        win["-PG_NAME-"].update("")

        sg.popup("Page supprimée.")
        return True


    return False
