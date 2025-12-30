# ui/ui_admin/systems_admin.py
# -*- coding: utf-8 -*-

import PySimpleGUI as sg
from ui.ui_paths_helpers import SYSTEMS, MATRIX, save_json
from ui.tabs.ui_tabs_admin import refresh_systems_table, refresh_matrix_table

def handle_systems_events(ev, vals, win, systems, matrix_rows):

    """
    GÈRE 100% DE LA LOGIQUE 'SYSTEMS' provenant de app.py :

    -SYS_TABLE-
    -S_SAVE-
    -S_DEL-

    ⚠️ Aucun affichage n'est créé ici.
    ⚠️ Ce module fait UNIQUEMENT la logique.
    """

    # ======================================================================
    # 🔥 1) Sélection dans la table Systems
    # ======================================================================
    if ev == "-SYS_TABLE-":
        sel = vals["-SYS_TABLE-"]
        if sel:
            idx = sel[0]
            keys = [k for k, _ in sorted(systems.items())]

            if idx < len(keys):
                key = keys[idx]
                val = systems[key]

                # On récupère les times
                if isinstance(val, list):
                    times = val
                else:
                    # Cas rare (ancienne structure dict)
                    times = val.get("times", [])

                win["-S_KEY-"].update(key)
                win["-S_TIMES-"].update(",".join(times))
                win["-S_KEY_ORIG-"].update(key)  # 👈 on mémorise l’ancien nom

        return True

    # ======================================================================
    # 🔥 2) S_ADD : ajouter un NOUVEAU system
    # ======================================================================
    if ev == "-S_ADD-":
        key = (vals.get("-S_KEY-") or "").strip()

        if not key:
            sg.popup_error("Le champ 'key' est obligatoire.")
            return True

        if key in systems:
            sg.popup_error(f"Le system '{key}' existe déjà. Utilise 'Update' pour le modifier.")
            return True

        raw = (vals.get("-S_TIMES-") or "").strip()
        times = [t.strip() for t in raw.split(",") if t.strip()]

        systems[key] = times

        save_json(SYSTEMS, {"systems": systems})
        refresh_systems_table(win, systems)

        sg.popup(f"System '{key}' ajouté.")
        return True

    # ======================================================================
    # 🔥 3) S_UPDATE : renommer / modifier un system existant
    # ======================================================================
    if ev == "-S_UPDATE-":
        new_key = (vals.get("-S_KEY-") or "").strip()
        old_key = (vals.get("-S_KEY_ORIG-") or "").strip()

        if not old_key:
            sg.popup_error("Sélectionne d'abord un system dans la liste.")
            return True

        if not new_key:
            sg.popup_error("Le champ 'key' est obligatoire.")
            return True

        raw = (vals.get("-S_TIMES-") or "").strip()
        times = [t.strip() for t in raw.split(",") if t.strip()]

        # ---- Cas 1 : même clé → on ne fait que mettre à jour les heures
        if new_key == old_key:
            systems[old_key] = times

        else:
            # ---- Cas 2 : renommage de la clé
            # Optionnel : protection si new_key existe déjà
            if new_key in systems and new_key != old_key:
                if sg.popup_yes_no(
                    f"Le system '{new_key}' existe déjà. Le remplacer ?"
                ) != "Yes":
                    return True

            # 1) Mise à jour du dict systems
            systems.pop(old_key, None)
            systems[new_key] = times

            # 2) Propagation dans MATRIX : renommer toutes les lignes
            for r in matrix_rows:
                if r.get("system") == old_key:
                    r["system"] = new_key

            # Sauvegarder Matrix + refresh
            save_json(MATRIX, {"rows": matrix_rows})
            refresh_matrix_table(win, matrix_rows)

        # 3) Sauvegarde des systems + refresh de l'onglet Systems (+ combos Albums/Matrix)
        save_json(SYSTEMS, {"systems": systems})
        refresh_systems_table(win, systems)

        # Mettre à jour la valeur d'origine pour un prochain rename
        win["-S_KEY_ORIG-"].update(new_key)

        sg.popup(f"System '{old_key}' mis à jour.")
        return True

    # ======================================================================
    # 🔥 4) S_DEL : supprimer un system + ses lignes Matrix
    # ======================================================================
    if ev == "-S_DEL-":
        key = (vals.get("-S_KEY-") or "").strip()

        if not key or key not in systems:
            sg.popup_error("Sélectionne un system existant.")
            return True

        if sg.popup_yes_no(
            f"Supprimer le system '{key}' ET toutes les lignes Matrix associées ?"
        ) != "Yes":
            return True

        # 1) Supprimer dans systems
        systems.pop(key, None)
        save_json(SYSTEMS, {"systems": systems})
        refresh_systems_table(win, systems)

        # 2) Supprimer les lignes Matrix qui utilisent ce system
        new_rows = [r for r in matrix_rows if r.get("system") != key]
        if len(new_rows) != len(matrix_rows):
            matrix_rows[:] = new_rows
            save_json(MATRIX, {"rows": matrix_rows})
            refresh_matrix_table(win, matrix_rows)

        # 3) Nettoyage des champs
        win["-S_KEY-"].update("")
        win["-S_KEY_ORIG-"].update("")
        win["-S_TIMES-"].update("")

        sg.popup("System et lignes Matrix associées supprimés.")
        return True
