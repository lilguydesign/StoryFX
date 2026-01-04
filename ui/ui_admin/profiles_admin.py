# ui/ui_admin/profiles_admin.py
# -*- coding: utf-8 -*-

import PySimpleGUI as sg
from ui.ui_paths_helpers import PROFILES, save_json, build_devices_map_from_profiles
from ui.tabs.ui_tabs_admin import refresh_profiles_table

PROF_SORT_KEY = "name"
PROF_SORT_ASC = True
PROF_VIEW_NAMES = []   # <- mapping index table -> profile name

def _profile_sort_value(name: str, cfg: dict, counts: dict, sort_key: str):
    if sort_key == "enabled":
        return 1 if cfg.get("enabled", True) else 0
    if sort_key == "name":
        return name.lower()
    if sort_key == "rows":
        return int(counts.get(name, 0))
    # autres champs “cfg”
    v = cfg.get(sort_key, "")
    # ports / offset -> int si possible
    if sort_key in ("tcpip_port", "offset_minutes"):
        try: return int(v)
        except Exception: return 0
    return str(v).lower()

def handle_profiles_events(ev, vals, win, profiles, matrix_rows):
    """
    GÈRE 100% DE LA LOGIQUE 'PROFILES' provenant du app.py ORIGINAL :

    -PROF_TABLE-
    -P_SAVE-
    -P_DEL-
    -P_DUP-
    -P_REFRESH-
    -P_PASTE_SERIAL-

    Aucun widget n’est créé ici.
    Ce module ne contient QUE la logique.
    """

    # ======================================================================
    # 🔥 1) Sélection d'un profil dans la table
    # ======================================================================
    if ev == "-PROF_TABLE-":
        sel = vals.get("-PROF_TABLE-")
        if not sel:
            return True

        idx = sel[0]
        names = getattr(win, "_prof_view_names", None) or sorted(profiles.keys())
        if idx >= len(names):
            return True

        name = names[idx]

        cfg = profiles.get(name, {})

        win["-P_NAME-"].update(name)
        win["-P_NAME_ORIG-"].update(name)
        win["-P_DEVICE-"].update(cfg.get("device_id", ""))
        win["-P_ADB_SERIAL-"].update(cfg.get("adb_serial", ""))
        win["-P_TCPIP_IP-"].update(cfg.get("tcpip_ip", ""))
        win["-P_TCPIP_PORT-"].update(str(cfg.get("tcpip_port", "")))
        win["-P_PVER-"].update(cfg.get("platform_version", ""))
        win["-P_OFFSET-"].update(str(cfg.get("offset_minutes", 0)))
        win["-P_ENABLED-"].update(bool(cfg.get("enabled", True)))

        # ✅ appium_overrides affiché en JSON dans l'UI
        app_ov = cfg.get("appium_overrides", {})
        try:
            import json
            win["-P_APPIUM_OVERRIDES-"].update(json.dumps(app_ov, ensure_ascii=False, indent=2))
        except Exception:
            win["-P_APPIUM_OVERRIDES-"].update("")

        gal = cfg.get("gallery", {}) or {}
        win["-P_GALLERY_PKG-"].update(gal.get("appPackage", "com.sec.android.gallery3d"))
        win["-P_GALLERY_ACT-"].update(gal.get("appActivity", "com.sec.android.gallery3d.app.GalleryActivity"))

        return True

    # ======================================================================
    # 🔥 1 bis) Sort d'un profil dans la table
    # ======================================================================

    if ev == "-P_SORT-":
        global PROF_SORT_KEY, PROF_SORT_ASC, PROF_VIEW_NAMES

        PROF_SORT_KEY = vals.get("-P_SORT_KEY-", "name")
        PROF_SORT_ASC = bool(vals.get("-P_SORT_ASC-", True))

        # compter rows (colonne "rows" = nb de lignes Matrix par profil)
        from collections import Counter
        counts = Counter()
        for r in matrix_rows or []:
            dev = r.get("device")
            if dev:
                counts[dev] += 1

        names = list(profiles.keys())
        names.sort(
            key=lambda n: _profile_sort_value(n, profiles.get(n, {}), counts, PROF_SORT_KEY),
            reverse=not PROF_SORT_ASC,
        )

        # ✅ stocker le mapping dans la window
        win._prof_view_names = names

        refresh_profiles_table(win, profiles, matrix_rows)
        return True

    # ======================================================================
    # 🔥 2) Ajouter ou mettre à jour un profil
    # ======================================================================
    if ev == "-P_SAVE-":
        import copy

        # Nouveau nom (champ visible)
        new_name = (vals.get("-P_NAME-") or "").strip()
        if not new_name:
            sg.popup_error("Le champ 'name' est obligatoire.")
            return True

        # Ancien nom (champ caché, défini quand on clique une ligne)
        old_name = (vals.get("-P_NAME_ORIG-") or "").strip()
        if not old_name:
            old_name = new_name  # création ou update simple

        is_rename = (old_name != new_name)

        # Si rename, vérifier collision
        if is_rename and new_name in profiles:
            sg.popup_error("Ce nom existe déjà.")
            return True

        # ✅ On part TOUJOURS de l’ancien profil sélectionné si rename
        base_cfg = profiles.get(old_name, {}) if old_name in profiles else profiles.get(new_name, {})
        cfg = copy.deepcopy(base_cfg) if isinstance(base_cfg, dict) else {}

        # Ancienne config pour propagation éventuelle
        prev_cfg = cfg.copy()
        old_device_id = prev_cfg.get("device_id")
        old_adb_serial = prev_cfg.get("adb_serial")

        # ✅ enabled
        cfg["enabled"] = bool(vals.get("-P_ENABLED-", True))

        # Champs standard
        device_id = (vals.get("-P_DEVICE-") or "").strip()
        adb_serial = (vals.get("-P_ADB_SERIAL-") or "").strip()
        tcpip_ip = (vals.get("-P_TCPIP_IP-") or "").strip()
        tcpip_port_raw = (vals.get("-P_TCPIP_PORT-") or "").strip()
        pver = (vals.get("-P_PVER-") or "").strip()

        try:
            tcpip_port = int(tcpip_port_raw) if tcpip_port_raw else None
        except Exception:
            tcpip_port = None

        try:
            offset_minutes = int((vals.get("-P_OFFSET-") or "0").strip())
        except Exception:
            offset_minutes = 0

        cfg.update({
            "device_id": device_id,
            "platform_version": pver,
            "offset_minutes": offset_minutes,
        })

        if adb_serial:
            cfg["adb_serial"] = adb_serial
        else:
            cfg.pop("adb_serial", None)

        if tcpip_ip:
            cfg["tcpip_ip"] = tcpip_ip
        else:
            cfg.pop("tcpip_ip", None)

        if tcpip_port is not None:
            cfg["tcpip_port"] = tcpip_port
        else:
            cfg.pop("tcpip_port", None)

        # ✅ appium_overrides vient du FRONT (multiline JSON)
        raw_ov = (vals.get("-P_APPIUM_OVERRIDES-") or "").strip()
        if raw_ov:
            try:
                import json
                parsed = json.loads(raw_ov)
                if not isinstance(parsed, dict):
                    sg.popup_error("appium_overrides doit être un JSON objet (clé/valeur).")
                    return True
                cfg["appium_overrides"] = parsed
            except Exception:
                sg.popup_error("appium_overrides invalide : JSON incorrect.")
                return True
        else:
            cfg.pop("appium_overrides", None)

        # ✅ gallery
        pkg = (vals.get("-P_GALLERY_PKG-") or "").strip()
        act = (vals.get("-P_GALLERY_ACT-") or "").strip()

        if pkg or act:
            cfg["gallery"] = {
                "appPackage": pkg or "com.sec.android.gallery3d",
                "appActivity": act or "com.sec.android.gallery3d.app.GalleryActivity",
            }
        else:
            cfg.pop("gallery", None)

        # ✅ écrire sous le nouveau nom
        profiles[new_name] = cfg

        # ✅ si rename : supprimer l'ancien
        if is_rename:
            profiles.pop(old_name, None)

            # ✅ (recommandé) Propager dans Matrix.device pour ne pas casser les jobs
            for r in (matrix_rows or []):
                if r.get("device") == old_name:
                    r["device"] = new_name

        # ==========================================================
        # 🔁 PROPAGATION : device_id / tcpip_ip / tcpip_port (OPTIONNEL)
        # ==========================================================
        if vals.get("-P_PROP_DEVICE-", False):
            # On propage seulement si device_id a réellement changé
            if old_device_id and device_id and device_id != old_device_id:
                for other_name, other_cfg in profiles.items():
                    if other_name == new_name:
                        continue

                    # même "ancien device_id" => on met à jour
                    if other_cfg.get("device_id") == old_device_id:
                        other_cfg["device_id"] = device_id

                        # si l'IP est vide, on n'écrase pas (on laisse la valeur existante)
                        if tcpip_ip:
                            other_cfg["tcpip_ip"] = tcpip_ip

                        # si port est None, on n'écrase pas (on laisse la valeur existante)
                        if tcpip_port is not None:
                            other_cfg["tcpip_port"] = tcpip_port

        # ==========================================================
        # 🔁 PROPAGATION : adb_serial
        # ==========================================================
        if vals.get("-P_PROP_SERIAL-", False):
            if old_adb_serial and adb_serial and adb_serial != old_adb_serial:
                for other_name, other_cfg in profiles.items():
                    if other_name == new_name:
                        continue
                    if other_cfg.get("adb_serial") == old_adb_serial:
                        other_cfg["adb_serial"] = adb_serial

        # Sauvegarder JSON
        save_json(PROFILES, {"profiles": profiles})

        refresh_profiles_table(win, profiles, matrix_rows)

        win["-P_NAME_ORIG-"].update(new_name)

        if "-M_DEVICE-" in win.AllKeysDict:
            win["-M_DEVICE-"].update(values=sorted(profiles.keys()))

        # garder sélection
        names = getattr(win, "_prof_view_names", None) or sorted(profiles.keys())
        try:
            idx = names.index(new_name)
        except ValueError:
            idx = None

        if idx is not None:
            try:
                win["-PROF_TABLE-"].update(select_rows=[idx])
                win["-PROF_TABLE-"].Widget.see(idx)
                win["-PROF_TABLE-"].set_focus()
                win.refresh()
            except Exception:
                pass

        # Rafraîchir la Combo -PROFILE-
        win["-PROFILE-"].update(values=sorted(profiles.keys()), value=new_name)

        # Mise à jour map devices pour d'autres modules
        build_devices_map_from_profiles(profiles)

        sg.popup("Profil enregistré.")
        return True

    # ======================================================================
    # 🔥 3) SUPPRESSION d'un profil
    # ======================================================================
    if ev == "-P_DEL-":
        name = (vals.get("-P_NAME-") or "").strip()

        if not name or name not in profiles:
            sg.popup_error("Sélectionne un profil existant.")
            return True

        if sg.popup_yes_no(f"Supprimer le profil '{name}' ?") != "Yes":
            return True

        profiles.pop(name, None)

        save_json(PROFILES, {"profiles": profiles})
        refresh_profiles_table(win, profiles, matrix_rows)
        win["-PROFILE-"].update(values=list(profiles.keys()))
        win["-M_DEVICE-"].update(values=sorted(profiles.keys()))

        # Reset UI
        win["-P_NAME-"].update("")
        win["-P_DEVICE-"].update("")
        win["-P_ADB_SERIAL-"].update("")
        win["-P_TCPIP_IP-"].update("")
        win["-P_TCPIP_PORT-"].update("")
        win["-P_PVER-"].update("")
        win["-P_OFFSET-"].update("0")
        win["-P_ENABLED-"].update(True)
        win["-P_APPIUM_OVERRIDES-"].update("")
        win["-P_GALLERY_PKG-"].update("")
        win["-P_GALLERY_ACT-"].update("")

        return True

    # ======================================================================
    # 🔥 4) DUPLICATION d’un profil
    # ======================================================================
    if ev == "-P_DUP-":
        sel = vals.get("-PROF_TABLE-", [])

        if not sel:
            sg.popup_error("Sélectionne d'abord un profil à dupliquer.")
            return True

        idx = sel[0]

        # ✅ ordre affiché (tri actif) sinon fallback
        names = getattr(win, "_prof_view_names", None) or sorted(profiles.keys())

        if idx >= len(names):
            return True

        import copy
        base_name = names[idx]
        base_cfg = copy.deepcopy(profiles.get(base_name, {}))

        new_name = sg.popup_get_text(
            f"Nouveau profil (copie de {base_name}):",
            default_text=f"{base_name}_copy"
        )

        if not new_name:
            return True

        new_name = new_name.strip()

        if not new_name:
            return True

        if new_name in profiles:
            sg.popup_error("Ce nom existe déjà.")
            return True

        # ✅ créer la copie
        profiles[new_name] = base_cfg

        # ✅ persister
        save_json(PROFILES, {"profiles": profiles})

        # ✅ refresh table
        refresh_profiles_table(win, profiles, matrix_rows)

        # ✅ refresh combo profiles (si tu veux garder tri alpha)
        win["-PROFILE-"].update(values=sorted(profiles.keys()), value=new_name)

        # ✅ recalculer l'ordre affiché (après refresh, car le tri peut déplacer la ligne)
        names = getattr(win, "_prof_view_names", None) or sorted(profiles.keys())

        # ✅ trouver index réel du nouveau profil dans l'ordre affiché
        try:
            new_idx = names.index(new_name)
        except ValueError:
            new_idx = None

        # ✅ sélectionner + scroll + focus (comme Matrix)
        if new_idx is not None:
            try:
                win["-PROF_TABLE-"].update(select_rows=[new_idx])
            except Exception:
                pass
            try:
                win["-PROF_TABLE-"].Widget.see(new_idx)
            except Exception:
                pass
            try:
                win["-PROF_TABLE-"].set_focus()
            except Exception:
                pass
            try:
                win.refresh()
            except Exception:
                pass

        # ✅ remplir la fiche en bas avec la config du nouveau profil (pas base_cfg “à l’aveugle”)
        cfg = profiles.get(new_name, {}) or {}
        gal = cfg.get("gallery", {}) or {}
        app_ov = cfg.get("appium_overrides", {}) or {}

        try:
            import json
            win["-P_APPIUM_OVERRIDES-"].update(json.dumps(app_ov, ensure_ascii=False, indent=2))
        except Exception:
            win["-P_APPIUM_OVERRIDES-"].update("")

        win["-P_GALLERY_PKG-"].update(gal.get("appPackage", "com.sec.android.gallery3d"))
        win["-P_GALLERY_ACT-"].update(gal.get("appActivity", "com.sec.android.gallery3d.app.GalleryActivity"))

        sg.popup(f"Profil dupliqué sous '{new_name}'.")
        return True

    # ======================================================================
    # 🔥 5) Coller un serial depuis le presse-papiers
    # ======================================================================
    if ev == "-P_PASTE_SERIAL-":
        try:
            clip = sg.clipboard_get() or ""
        except Exception:
            clip = ""

        serial = clip.strip()
        if not serial:
            sg.popup_error("Aucun serial trouvé dans le presse-papiers.")
        else:
            win["-P_ADB_SERIAL-"].update(serial)

        return True

    # ======================================================================
    # 🔥 6) Rafraîchir la table Profiles
    # ======================================================================
    if ev == "-P_REFRESH-":
        refresh_profiles_table(win, profiles, matrix_rows)
        return True

    # ======================================================================
    # Aucun événement profile
    # ======================================================================
    return False
