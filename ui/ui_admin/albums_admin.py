# ui/ui_admin/albums_admin.py
# -*- coding: utf-8 -*-

import PySimpleGUI as sg

from ui.ui_paths_helpers import (
    MATRIX,
    save_json,
    load_albums_dict,
    save_albums_dict,
    INTRO_ALBUM_CHOICES,
    MULTI_ALBUM_CHOICES,
)
from ui.tabs.ui_tabs_admin import (
    refresh_albums_table,
    refresh_matrix_table,
)


def handle_albums_events(ev, vals, win, albums_dict, matrix_rows, profiles):
    """
    GÈRE 100% DE LA LOGIQUE ALBUMS provenant de ton app.py :

        -ALB_TABLE-
        -ALB_NEW-
        -ALB_SAVE-
        -ALB_DEL-
        -ALB_SYNC-

    Aucun widget n’est créé ici : seulement de la logique.
    """

    # ======================================================================
    # 🔥 1) Sélection dans la table Albums
    # ======================================================================
    if ev == "-ALB_TABLE-":
        sel = vals.get("-ALB_TABLE-", [])
        if sel:
            idx = sel[0]
            names = sorted(albums_dict.keys())

            if 0 <= idx < len(names):
                name = names[idx]
                cfg = albums_dict[name]

                win["-ALB_NAME-"].update(name)
                win["-ALB_KIND-"].update(cfg.get("kind", "multi"))
                win["-ALB_SIZE-"].update(str(cfg.get("album_size", 0)))
                win["-ALB_COUNT-"].update(str(cfg.get("count_per_post", 0)))
                win["-ALB_SYSTEM-"].update(cfg.get("default_system", ""))
                win["-ALB_ENGINE_FULL-"].update(cfg.get("engine_full", "multi"))
                win["-ALB_INTRO_TMP-"].update(cfg.get("intro_album", ""))

                # 🔥 Profils associés à cet album : on les coche dans la Listbox
                if isinstance(profiles, dict) and "profiles" in profiles:
                    profiles_dict = profiles["profiles"]
                else:
                    profiles_dict = profiles or {}

                all_profile_names = sorted(profiles_dict.keys())
                win["-ALB_DEVICES-"].update(values=all_profile_names)

                selected = cfg.get("profiles", []) or []
                indices = [i for i, n in enumerate(all_profile_names) if n in selected]
                if indices:
                    win["-ALB_DEVICES-"].update(set_to_index=indices)
                else:
                    win["-ALB_DEVICES-"].update(set_to_index=[])

                # 🔥 Très important : mémoriser l’ancien nom !
                win["-ALB_NAME_ORIG-"].update(name)

        return True

    # ======================================================================
    # 🔥 1 bis) Bouton "Nouveau" : réinitialiser le formulaire
    # ======================================================================
    if ev == "-ALB_NEW-":
        # On vide les champs pour préparer la création d’un nouvel album
        win["-ALB_NAME-"].update("")
        win["-ALB_KIND-"].update("multi")
        win["-ALB_SIZE-"].update("0")
        win["-ALB_COUNT-"].update("0")
        win["-ALB_NAME_ORIG-"].update("")


        # On ne touche NI à albums_dict NI à matrix_rows ici.
        # La création réelle se fera quand tu cliqueras sur -ALB_SAVE-.
        return True

    # ======================================================================
    # 🔥 1 ter) Bouton "Tous" : sélectionner tous les profils
    # ======================================================================
    if ev == "-ALB_SELECT_ALL_PROF-":

        # Récupérer la dict des profils
        if isinstance(profiles, dict) and "profiles" in profiles:
            profiles_dict = profiles["profiles"]
        else:
            profiles_dict = profiles or {}

        # On prend TOUS les profils (actifs + inactifs)
        profile_names = sorted(profiles_dict.keys())

        # Mettre la liste + tout sélectionner
        win["-ALB_DEVICES-"].update(
            values=profile_names,
            set_to_index=list(range(len(profile_names)))  # coche tous les indices
        )

        return True

    # ======================================================================
    # 🔥 2) Enregistrer un album
    # ======================================================================
    if ev == "-ALB_SAVE-":
        name = (vals.get("-ALB_NAME-") or "").strip()
        if not name:
            sg.popup_error("Choisis ou saisis un nom d’album.")
            return True

        kind = (vals.get("-ALB_KIND-") or "multi").strip() or "multi"

        try:
            album_size = int((vals.get("-ALB_SIZE-") or "0").strip())
        except:
            album_size = 0

        try:
            count_per_post = int((vals.get("-ALB_COUNT-") or "0").strip())
        except:
            count_per_post = 0

        # NOM AVANT CHANGEMENT (pour rename global)
        old_name = (vals.get("-ALB_NAME_ORIG-") or "").strip()
        if not old_name:
            old_name = name  # aucun ancien nom → cas "nouvel album"


        # Nouveaux champs persistés avec l'album
        default_system = (vals.get("-ALB_SYSTEM-") or "").strip()
        engine_full = (vals.get("-ALB_ENGINE_FULL-") or "multi").strip()
        intro_album = (vals.get("-ALB_INTRO_TMP-") or "").strip()
        # Profils associés à cet album (liste de noms)
        selected_profiles = vals.get("-ALB_DEVICES-", []) or []


        # ==========================================================
        # 🔥 RENOMMAGE GLOBAL si old_name différent
        # ==========================================================
        if old_name and old_name != name and old_name in albums_dict:

            # 1) Rename dans albums_dict
            albums_dict.pop(old_name)
            albums_dict[name] = {
                "kind": kind,
                "album_size": album_size,
                "count_per_post": count_per_post,
                "default_system": default_system,
                "engine_full": engine_full,
                "intro_album": intro_album,
                "profiles": selected_profiles,
            }

            # 2) Mise à jour Matrix
            for r in matrix_rows:
                if r.get("album") == old_name:
                    r["album"] = name
                if r.get("album2") == old_name:
                    r["album2"] = name

            save_json(MATRIX, {"rows": matrix_rows})
            refresh_matrix_table(win, matrix_rows)

        else:
            # ======================================================
            # 🔥 Mode normal : création / update simple d’un album
            # ======================================================
            albums_dict[name] = {
                "kind": kind,
                "album_size": album_size,
                "count_per_post": count_per_post,
                "default_system": default_system,
                "engine_full": engine_full,
                "intro_album": intro_album,
                "profiles": selected_profiles,
            }


        # 3) Sauvegarde finale
        save_albums_dict(albums_dict)
        refresh_albums_table(win, albums_dict)

        # ======================================================
        # 🔥 Synchronisation automatique si album MULTI
        # ======================================================
        if kind == "multi":
            for r in matrix_rows:
                if r.get("album2") == name:
                    r["count"] = count_per_post

            save_json(MATRIX, {"rows": matrix_rows})
            refresh_matrix_table(win, matrix_rows)

        # ======================================================
        # 🔥 Mise à jour combos intro/multi
        # ======================================================
        intro_list = sorted(
            n for n, cfg in albums_dict.items()
            if cfg.get("kind", "multi") == "intro"
        )
        multi_list = sorted(
            n for n, cfg in albums_dict.items()
            if cfg.get("kind", "multi") == "multi"
        )

        win["-ALBUM-"].update(values=intro_list)
        win["-ALBUM2-"].update(values=multi_list)
        win["-M_ALBUM-"].update(values=intro_list)
        win["-M_ALBUM2-"].update(values=multi_list)

        sg.popup("Album enregistré.")
        return True

    # ======================================================================
    # 🔥 3) Supprimer un album
    # ======================================================================
    if ev == "-ALB_DEL-":
        name = (vals.get("-ALB_NAME-") or "").strip()

        if not name or name not in albums_dict:
            sg.popup_error("Sélectionne un album existant.")
            return True

        if sg.popup_yes_no(f"Supprimer l’album '{name}' ?") != "Yes":
            return True

        # 1) Supprimer dans albums.json
        albums_dict.pop(name, None)
        save_albums_dict(albums_dict)
        refresh_albums_table(win, albums_dict)

        # 2) Supprimer les lignes matrix qui utilisent cet album
        new_rows = []
        for r in matrix_rows:
            if r.get("album") == name or r.get("album2") == name:
                continue
            new_rows.append(r)

        matrix_rows[:] = new_rows
        save_json(MATRIX, {"rows": matrix_rows})
        refresh_matrix_table(win, matrix_rows)

        # 3) Nettoyage combos
        intro_list = sorted(
            n for n, cfg in albums_dict.items()
            if cfg.get("kind", "multi") == "intro"
        )
        multi_list = sorted(
            n for n, cfg in albums_dict.items()
            if cfg.get("kind", "multi") == "multi"
        )

        win["-ALBUM-"].update(values=intro_list, value="")
        win["-ALBUM2-"].update(values=multi_list, value="")
        win["-M_ALBUM-"].update(values=intro_list, value="")
        win["-M_ALBUM2-"].update(values=multi_list, value="")

        # 4) Nettoyage champs
        win["-ALB_NAME-"].update("")
        win["-ALB_KIND-"].update("")
        win["-ALB_SIZE-"].update("0")
        win["-ALB_COUNT-"].update("0")

        sg.popup("Album supprimé.")
        return True

    # ======================================================================
    # 🔥 4) Envoyer cet album dans Matrix pour un ou plusieurs profils
    # ======================================================================

    if ev == "-ALB_PUSH_ALL-":

        album_name = (vals.get("-ALB_NAME-") or "").strip()
        if not album_name:
            sg.popup_error("Choisis un album.")
            return True

        cfg = albums_dict.get(album_name)
        if not cfg:
            sg.popup_error("Album introuvable dans albums.json.")
            return True

        system = (vals.get("-ALB_SYSTEM-") or "").strip()
        if not system:
            sg.popup_error("Choisis un system.")
            return True

        # 🔥 profils réellement sélectionnés dans la Listbox
        selected_profiles = vals.get("-ALB_DEVICES-", []) or []
        if not selected_profiles:
            # Si rien n'est sélectionné manuellement, on prend les profils mémorisés
            selected_profiles = cfg.get("profiles", []) or []

        if not selected_profiles:
            sg.popup_error("Sélectionne au moins un profil.")
            return True


        engine_full = (vals.get("-ALB_ENGINE_FULL-") or "multi").strip()

        # Si intro+multi → on doit aussi connaître l'album intro
        intro_album = None
        if engine_full == "intro+multi":
            intro_album = (vals.get("-ALB_INTRO_TMP-") or "").strip()
            if not intro_album:
                sg.popup_error("Choisis un album intro pour 'intro+multi'.")
                return True

        album_size = int(cfg.get("album_size", 0) or 0)
        count = int(cfg.get("count_per_post", 0) or 0)

        created = 0

        for prof in selected_profiles:

            # 💡 Anti-doublon : on vérifie si une ligne similaire existe déjà
            already = any(
                (r.get("device") == prof) and
                (r.get("system") == system) and
                (
                    (engine_full == "intro"      and r.get("album")  == album_name) or
                    (engine_full == "multi"      and r.get("album2") == album_name) or
                    (engine_full == "intro+multi" and r.get("album2") == album_name)
                )
                for r in matrix_rows
            )
            if already:
                continue

            row = {
                "device": prof,
                "system": system,
                "engine": engine_full,
                "platform": "WhatsApp",
                "page": "",
                "page_name": "",
                "album_size": album_size,
                "count": count,
            }


            if engine_full == "intro":
                row["album"] = album_name
                row["album2"] = ""
            elif engine_full == "multi":
                row["album"] = ""
                row["album2"] = album_name
            elif engine_full == "intro+multi":
                row["album"] = intro_album
                row["album2"] = album_name

            matrix_rows.append(row)
            created += 1

        if created > 0:
            save_json(MATRIX, {"rows": matrix_rows})
            refresh_matrix_table(win, matrix_rows)
            sg.popup(f"{created} ligne(s) ajoutée(s) dans Matrix.")
        else:
            sg.popup("Aucune ligne ajoutée (elles existent peut-être déjà).")

        return True

    # ======================================================================
    # 🔥 5) Renommer un album dans Matrix
    # ======================================================================
    if ev == "-ALB_RENAME_MATRIX-":

        old_name = vals.get("-ALB_NAME_ORIG-", "").strip()
        new_name = vals.get("-ALB_NAME-", "").strip()

        if not old_name or not new_name:
            sg.popup_error("Ancien ou nouveau nom invalide.")
            return True

        if old_name == new_name:
            sg.popup("Aucun changement à appliquer.")
            return True

        changed = 0

        for row in matrix_rows:
            # intro engine → champ album
            if row.get("album") == old_name:
                row["album"] = new_name
                changed += 1

            # multi engine → champ album2
            if row.get("album2") == old_name:
                row["album2"] = new_name
                changed += 1

        if changed > 0:
            save_json(MATRIX, {"rows": matrix_rows})
            refresh_matrix_table(win, matrix_rows)
            sg.popup(f"Album renommé dans {changed} ligne(s) Matrix.")
        else:
            sg.popup("Aucune entrée Matrix ne contenait cet album.")

        return True

    # ======================================================================
    # 🔥 6) Synchronisation : albums multi → Matrix
    # ======================================================================
    if ev == "-ALB_SYNC-":

        for name, cfg in albums_dict.items():
            if cfg.get("kind") == "multi":
                count = cfg.get("count_per_post", 0)

                for r in matrix_rows:
                    if r.get("album2") == name:
                        r["count"] = count

        save_json(MATRIX, {"rows": matrix_rows})
        refresh_matrix_table(win, matrix_rows)

        sg.popup("Synchronisation Matrix OK.")
        return True

    # ======================================================================
    # Aucun event Albums
    # ======================================================================
    return False
