# ui/ui_admin/matrix_admin.py
# -*- coding: utf-8 -*-

import PySimpleGUI as sg
from ui.ui_paths_helpers import MATRIX, save_json
from ui.ui_paths_helpers import INTRO_ALBUM_CHOICES, MULTI_ALBUM_CHOICES
from ui.tabs.ui_tabs_admin import refresh_matrix_table


def handle_matrix_events(ev, vals, win, matrix_rows, albums_dict):
    """
    GÈRE 100% DE LA LOGIQUE 'MATRIX' provenant de app.py :

    -MAT_TABLE-
    -M_SAVE-
    -M_DEL-
    -M_REFRESH-

    ⚠ Aucun widget n'est créé ici.
    ⚠ Logique pure et propre.
    """

    # ======================================================================
    # 🔥 1) Sélection dans la TABLE Matrix
    # ======================================================================
    if ev == "-MAT_TABLE-":
        sel = vals["-MAT_TABLE-"]
        if sel:
            idx = sel[0]
            if 0 <= idx < len(matrix_rows):

                r = matrix_rows[idx]

                win["-M_DEVICE-"].update(r.get("device", ""))
                win["-M_SYSTEM-"].update(r.get("system", ""))
                win["-M_ENGINE-"].update(r.get("engine", ""))

                win["-M_ALBUM-"].update(r.get("album", ""))
                win["-M_ALBUM2-"].update(r.get("album2", ""))

                win["-M_ALBUM_SIZE-"].update(str(r.get("album_size", 0)))
                win["-M_COUNT-"].update(str(r.get("count", 11)))

                win["-M_PLATFORM-"].update(r.get("platform", "WhatsApp"))
                win["-M_PAGE-"].update(r.get("page", ""))
                win["-M_PNAME-"].update(r.get("page_name", ""))

        return True

    # ======================================================================
    # 🔥 2) Ajout / Mise à jour d'une ligne MATRIX
    # ======================================================================
    if ev in ("-M_ADD-", "-M_UPDATE-"):

        data = {
            "device": (vals.get("-M_DEVICE-") or "").strip(),
            "system": (vals.get("-M_SYSTEM-") or "").strip(),
            "engine": (vals.get("-M_ENGINE-") or "").strip(),

            "album": (vals.get("-M_ALBUM-") or "").strip(),
            "album2": (vals.get("-M_ALBUM2-") or "").strip(),

            "platform": (vals.get("-M_PLATFORM-") or "").strip() or "WhatsApp",
            "page": (vals.get("-M_PAGE-") or "").strip(),       # Pays
            "page_name": (vals.get("-M_PNAME-") or "").strip(), # Page

        }

        # album_size
        try:
            data["album_size"] = int((vals.get("-M_ALBUM_SIZE-") or "0").strip())
        except Exception:
            data["album_size"] = 0

        # count
        try:
            data["count"] = int((vals.get("-M_COUNT-") or "11").strip())
        except Exception:
            data["count"] = 11

        sel = vals.get("-MAT_TABLE-", [])

        if ev == "-M_UPDATE-":
            if not sel:
                sg.popup_error("Sélectionne d'abord une ligne Matrix à mettre à jour.")
                return True
            idx = sel[0]
            if 0 <= idx < len(matrix_rows):
                matrix_rows[idx] = data
        else:  # -M_ADD-
            matrix_rows.append(data)

        # Sauvegarde
        save_json(MATRIX, {"rows": matrix_rows})
        refresh_matrix_table(win, matrix_rows)

        win["-M_ALBUM-"].update(values=INTRO_ALBUM_CHOICES)
        win["-M_ALBUM2-"].update(values=MULTI_ALBUM_CHOICES)


        sg.popup("Ligne Matrix ajoutée." if ev == "-M_ADD-" else "Ligne Matrix mise à jour.")
        return True

    # ======================================================================
    # 🔥 3) Suppression d'une ligne MATRIX
    # ======================================================================
    if ev == "-M_DEL-":
        sel = vals["-MAT_TABLE-"]

        if not sel:
            sg.popup_error("Sélectionne d'abord une ligne Matrix.")
            return True

        if sg.popup_yes_no("Supprimer la ligne sélectionnée ?") != "Yes":
            return True

        for idx in sorted(sel, reverse=True):
            if 0 <= idx < len(matrix_rows):
                del matrix_rows[idx]

        save_json(MATRIX, {"rows": matrix_rows})
        refresh_matrix_table(win, matrix_rows)

        # Recharger les combos albums si tu veux (facultatif)
        win["-ALBUM-"].update(values=INTRO_ALBUM_CHOICES)
        return True


    # ======================================================================
    # 🔥 4) Rafraîchissement complet (Albums → Matrix sync)
    # ======================================================================
    if ev == "-M_REFRESH-":

        # Synchroniser tous les albums multi vers Matrix
        for name, cfg in albums_dict.items():
            if cfg.get("kind") == "multi":
                count = cfg.get("count_per_post", 0)

                for r in matrix_rows:
                    if r.get("album2") == name:
                        r["count"] = count

        save_json(MATRIX, {"rows": matrix_rows})
        refresh_matrix_table(win, matrix_rows)

        sg.popup("Matrix synchronisée depuis Albums.")
        return True

    # ======================================================================
    # Aucun événement Matrix
    # ======================================================================
    return False
