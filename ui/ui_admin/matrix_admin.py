# ui/ui_admin/matrix_admin.py
# -*- coding: utf-8 -*-

import PySimpleGUI as sg
from ui.ui_paths_helpers import MATRIX, save_json
from ui.ui_paths_helpers import INTRO_ALBUM_CHOICES, MULTI_ALBUM_CHOICES
from ui.tabs.ui_tabs_admin import refresh_matrix_table


import copy

# ✅ Mapping des colonnes triables (UI -> champ JSON)
SORT_FIELDS = {
    "device": "device",
    "system": "system",
    "engine": "engine",
    "album intro": "album",
    "album multi": "album2",
    "platform": "platform",
    "pays": "page",
    "page_name": "page_name",
    "count": "count",
    "album_size": "album_size",
}

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
    # 🔥 1 bis) Trier la matrix (comme Excel)
    # ======================================================================
    if ev == "-M_SORT-":
        key_ui = (vals.get("-M_SORT_KEY-") or "device").strip()
        asc = bool(vals.get("-M_SORT_ASC-", True))

        field = SORT_FIELDS.get(key_ui, "device")

        def _norm(v):
            if v is None:
                return ""
            if isinstance(v, (int, float)):
                return v
            return str(v).strip().lower()

        matrix_rows.sort(key=lambda r: _norm(r.get(field)), reverse=not asc)

        save_json(MATRIX, {"rows": matrix_rows})
        refresh_matrix_table(win, matrix_rows)
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
                sg.popup_error("Sélectionne d'abord une ou plusieurs lignes Matrix à mettre à jour.")
                return True

            # ✅ Mettre à jour toutes les lignes sélectionnées
            multi_sel = len(sel) > 1

            for idx in sel:
                if 0 <= idx < len(matrix_rows):

                    # 1) Toujours : update device (c’est l’identifiant)
                    matrix_rows[idx]["device"] = data["device"]

                    # 2) Si multi-sélection : NE PAS écraser le reste
                    if multi_sel:
                        continue

                    # 3) Si sélection unique : update complet (comportement normal)
                    matrix_rows[idx]["system"] = data["system"]
                    matrix_rows[idx]["engine"] = data["engine"]
                    matrix_rows[idx]["album"] = data["album"]
                    matrix_rows[idx]["album2"] = data["album2"]
                    matrix_rows[idx]["platform"] = data["platform"]
                    matrix_rows[idx]["page"] = data["page"]
                    matrix_rows[idx]["page_name"] = data["page_name"]
                    matrix_rows[idx]["album_size"] = data.get("album_size", 0)
                    matrix_rows[idx]["count"] = data.get("count", 11)

            save_json(MATRIX, {"rows": matrix_rows})
            refresh_matrix_table(win, matrix_rows)

            sg.popup(f"{len(sel)} ligne(s) Matrix mise(s) à jour.")
            return True

    # ======================================================================
    # 🔥 3) Suppression d'une ou plusieurs lignes MATRIX
    # ======================================================================
    if ev == "-M_DEL-":
        sel = vals.get("-MAT_TABLE-", [])

        if not sel:
            sg.popup_error("Sélectionne au moins une ligne Matrix.")
            return True

        if sg.popup_yes_no(
                f"Supprimer {len(sel)} ligne(s) sélectionnée(s) ?"
        ) != "Yes":
            return True

        # 🔥 supprimer du bas vers le haut (sécurité index)
        for idx in sorted(sel, reverse=True):
            if 0 <= idx < len(matrix_rows):
                del matrix_rows[idx]

        save_json(MATRIX, {"rows": matrix_rows})
        refresh_matrix_table(win, matrix_rows)

        sg.popup("Ligne(s) Matrix supprimée(s).")
        return True

    # ======================================================================
    # 🔥 3 bis) Dupliquer une ou plusieurs lignes MATRIX
    # ======================================================================
    if ev == "-M_DUP-":
        sel = vals.get("-MAT_TABLE-", [])
        if not sel:
            sg.popup_error("Sélectionne au moins une ligne Matrix à dupliquer.")
            return True

        target_device = (vals.get("-M_DEVICE-") or "").strip()
        if not target_device:
            sg.popup_error("Choisis d'abord un device cible dans le combo 'device'.")
            return True

        # On mémorise l'index de départ AVANT ajout
        start_idx = len(matrix_rows)

        created = 0
        for idx in sel:
            if 0 <= idx < len(matrix_rows):
                new_row = copy.deepcopy(matrix_rows[idx])

                # ✅ changer le device vers celui choisi
                new_row["device"] = target_device

                # ✅ valeurs par défaut (si absentes)
                new_row.setdefault("platform", "WhatsApp")
                new_row.setdefault("page", "")
                new_row.setdefault("page_name", "")
                new_row.setdefault("album_size", 0)
                new_row.setdefault("count", 11)
                new_row.setdefault("album", "")
                new_row.setdefault("album2", "")

                matrix_rows.append(new_row)
                created += 1

        if created <= 0:
            sg.popup_error("Aucune ligne dupliquée (sélection invalide).")
            return True

        # ✅ indices des nouvelles lignes (ajoutées en bas)
        new_indices = list(range(start_idx, start_idx + created))

        # ✅ sauvegarde + refresh UNE SEULE FOIS
        save_json(MATRIX, {"rows": matrix_rows})
        refresh_matrix_table(win, matrix_rows)

        # ✅ sélectionner automatiquement les nouvelles lignes
        try:
            win["-MAT_TABLE-"].update(select_rows=new_indices)
        except Exception:
            pass

        # ✅ scroller vers la première nouvelle ligne
        try:
            win["-MAT_TABLE-"].Widget.see(new_indices[0])
        except Exception:
            pass

        # ✅ charger la 1ère nouvelle ligne dans les champs du bas
        try:
            r = matrix_rows[new_indices[0]]
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
        except Exception:
            pass

        # ✅ sélectionner automatiquement les nouvelles lignes
        try:
            win["-MAT_TABLE-"].update(select_rows=new_indices)
        except Exception:
            pass

        # ✅ forcer le focus (sinon Tk ignore parfois le scroll)
        try:
            win["-MAT_TABLE-"].set_focus()
        except Exception:
            pass

        # ✅ scroller vraiment vers la 1ère nouvelle ligne (robuste)
        try:
            table_widget = win["-MAT_TABLE-"].Widget
            total = len(matrix_rows)
            if total > 0:
                first = new_indices[0]
                # position entre 0.0 et 1.0
                frac = max(0.0, min(1.0, first / max(1, total - 1)))
                table_widget.yview_moveto(frac)  # 🔥 scroll “dur”
                table_widget.see(first)  # sécurité : s’assurer qu’elle est visible
        except Exception:
            pass

        # ✅ forcer un refresh UI (aide énormément)
        try:
            win.refresh()
        except Exception:
            pass

        sg.popup(f"{created} ligne(s) dupliquée(s) sur le device '{target_device}'.")
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
