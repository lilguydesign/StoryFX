# ui/ui_admin/profiles_admin.py
# -*- coding: utf-8 -*-

import PySimpleGUI as sg
from ui.ui_paths_helpers import PROFILES, save_json, build_devices_map_from_profiles
from ui.tabs.ui_tabs_admin import refresh_profiles_table


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
        names = [name for name, _ in sorted(profiles.items())]

        if idx >= len(names):
            return True

        name = names[idx]
        cfg = profiles.get(name, {})

        win["-P_NAME-"].update(name)
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

        return True

    # ======================================================================
    # 🔥 2) Ajouter ou mettre à jour un profil
    # ======================================================================
    if ev == "-P_SAVE-":
        name = (vals.get("-P_NAME-") or "").strip()
        if not name:
            sg.popup_error("Le champ 'name' est obligatoire.")
            return True

        # On part de l’existant (ou vide)
        cfg = profiles.get(name, {})

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

        profiles[name] = cfg

        # ==========================================================
        # 🔁 PROPAGATION : device_id / tcpip_ip / tcpip_port
        # ==========================================================
        if old_device_id and device_id and device_id != old_device_id:
            for other_name, other_cfg in profiles.items():
                if other_name == name:
                    continue

                if other_cfg.get("device_id") == old_device_id:
                    other_cfg["device_id"] = device_id

                    if tcpip_ip:
                        other_cfg["tcpip_ip"] = tcpip_ip
                    if tcpip_port:
                        other_cfg["tcpip_port"] = tcpip_port

        # ==========================================================
        # 🔁 PROPAGATION : adb_serial
        # ==========================================================
        if old_adb_serial and adb_serial and adb_serial != old_adb_serial:
            for other_name, other_cfg in profiles.items():
                if other_name == name:
                    continue

                if other_cfg.get("adb_serial") == old_adb_serial:
                    other_cfg["adb_serial"] = adb_serial

        # Sauvegarder JSON
        save_json(PROFILES, {"profiles": profiles})

        # Rafraîchir la table
        refresh_profiles_table(win, profiles, matrix_rows)

        # Rafraîchir la Combo -PROFILE-
        win["-PROFILE-"].update(values=list(profiles.keys()))

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

        # Reset UI
        win["-P_NAME-"].update("")
        win["-P_DEVICE-"].update("")
        win["-P_ADB_SERIAL-"].update("")
        win["-P_TCPIP_IP-"].update("")
        win["-P_TCPIP_PORT-"].update("")
        win["-P_PVER-"].update("")
        win["-P_OFFSET-"].update("0")
        win["-P_ENABLED-"].update(True)

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
        names = [name for name, _ in sorted(profiles.items())]

        if idx >= len(names):
            return True

        base_name = names[idx]
        base_cfg = profiles.get(base_name, {}).copy()

        new_name = sg.popup_get_text(
            f"Nouveau profil (copie de {base_name}):",
            default_text=f"{base_name}_copy"
        )

        if not new_name:
            return True

        new_name = new_name.strip()

        if new_name in profiles:
            sg.popup_error("Ce nom existe déjà.")
            return True

        profiles[new_name] = base_cfg

        save_json(PROFILES, {"profiles": profiles})
        refresh_profiles_table(win, profiles, matrix_rows)
        win["-PROFILE-"].update(values=list(profiles.keys()))

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
