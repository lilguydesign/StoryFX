"""Compile an owner-only legacy configuration preview without importing its engine."""

import hashlib
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PLATFORMS = {"WhatsApp", "Facebook", "Instagram", "TikTok"}
ENGINES = {"intro", "multi", "intro+multi"}
MAX_CONFIG_BYTES = 2 * 1024 * 1024


def _reference(value, prefix):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _read_config(folder, filename, member, expected):
    path = folder / filename
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError(f"Required configuration unavailable: {filename}")
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"Invalid configuration: {filename}") from exc
    result = document.get(member) if isinstance(document, dict) else None
    if not isinstance(result, expected):
        raise ValueError(f"Invalid configuration structure: {filename}")
    return result


def _integer(value, minimum, maximum):
    if isinstance(value, bool):
        raise ValueError("Expected an integer")
    result = int(value)
    if str(result) != str(value) or not minimum <= result <= maximum:
        raise ValueError("Integer out of range")
    return result


def _clock(value):
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
        raise ValueError("Expected HH:MM")
    hour = _integer(value[:2].lstrip("0") or "0", 0, 23)
    minute = _integer(value[3:].lstrip("0") or "0", 0, 59)
    if value != f"{hour:02d}:{minute:02d}":
        raise ValueError("Expected HH:MM")
    return hour * 60 + minute


def _label(value, fallback):
    return value if isinstance(value, str) and 0 < len(value) <= 160 else fallback[:160]


def _local_occurrence(day, minutes, zone):
    naive = datetime.combine(day, time(minutes // 60, minutes % 60))
    aware = naive.replace(tzinfo=zone)
    if aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != naive:
        raise ValueError("Schedule falls in a daylight-saving gap")
    if aware.utcoffset() != naive.replace(tzinfo=zone, fold=1).utcoffset():
        raise ValueError("Schedule is ambiguous during daylight-saving transition")
    return aware


def preview_legacy_plan(config_dir, *, reference_date=None, timezone_name="Africa/Douala"):
    """Read four fixed files; return inert jobs with transport-free opaque references.

    The caller must supply a trusted, server-configured folder. This function does
    not persist plans, connect phones, start schedulers, or publish anything.
    """
    try:
        zone = ZoneInfo(timezone_name)
        day = date.fromisoformat(reference_date) if reference_date else datetime.now(zone).date()
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        raise ValueError("Invalid preview date or timezone") from exc
    folder = Path(config_dir)
    profiles = _read_config(folder, "profiles.json", "profiles", dict)
    systems = _read_config(folder, "systems.json", "systems", dict)
    rows = _read_config(folder, "matrix.json", "rows", list)
    albums = _read_config(folder, "albums.json", "albums", list)
    warnings = [{"code": "physical_device_identity_unverified", "count": 1}]
    warning_counts = {}

    def warn(code):
        warning_counts[code] = warning_counts.get(code, 0) + 1

    album_lookup = {}
    for album in albums:
        if not isinstance(album, dict) or not isinstance(album.get("name"), str):
            warn("invalid_album")
            continue
        if album["name"] in album_lookup:
            warn("duplicate_album_name")
        album_lookup[album["name"]] = album
    devices = {}
    disabled = 0
    for name, profile in profiles.items():
        if not isinstance(profile, dict) or not isinstance(profile.get("enabled", True), bool):
            warn("invalid_profile")
            continue
        if not profile.get("enabled", True):
            disabled += 1
            continue
        try:
            offset = _integer(profile.get("offset_minutes", 0), -10080, 10080)
        except (ValueError, TypeError, OverflowError):
            warn("invalid_profile_offset")
            continue
        devices[name] = {
            "preview_device_id": _reference(name, "device_"),
            "label": _label(profile.get("label"), str(name)),
            "offset_minutes": offset,
        }
    jobs = []
    seen_ids = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            warn("invalid_matrix_row")
            continue
        name = row.get("device")
        if not isinstance(name, str) or name not in profiles:
            warn("orphan_device_row")
            continue
        if name not in devices:
            continue
        system_name = row.get("system")
        if not isinstance(system_name, str) or system_name not in systems:
            warn("orphan_system_row")
            continue
        system = systems[system_name]
        times = system.get("times") if isinstance(system, dict) else system
        if not isinstance(times, list):
            warn("invalid_system_times")
            continue
        engine, platform = row.get("engine"), row.get("platform", "WhatsApp")
        if (not isinstance(engine, str) or not isinstance(platform, str)
                or engine not in ENGINES or platform not in PLATFORMS):
            warn("unsupported_engine_or_platform")
            continue
        intro, multi = row.get("album") or "", row.get("album2") or ""
        selected_album = intro if engine == "intro" else multi or intro
        if not isinstance(intro, str) or not isinstance(multi, str) or not selected_album:
            warn("missing_album_reference")
            continue
        if selected_album not in album_lookup or (engine == "intro+multi" and intro not in album_lookup):
            warn("unregistered_album")
        album = album_lookup.get(selected_album, {})
        try:
            count = 1 if engine == "intro" else _integer(
                album.get("count_per_post") or row.get("count") or 0, 1, 1000)
        except (ValueError, TypeError, OverflowError):
            warn("invalid_post_count")
            continue
        business_fields = {key: row.get(key) for key in (
            "device", "system", "engine", "platform", "album", "album2", "count", "page", "page_name")}
        row_id = _reference([index, business_fields], "row_")
        for base_time in times:
            try:
                minute = (_clock(base_time) + devices[name]["offset_minutes"]) % 1440
                local = _local_occurrence(day, minute, zone)
            except (ValueError, TypeError, OverflowError):
                warn("invalid_or_ambiguous_schedule_time")
                continue
            due_at = local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            job_id = _reference([row_id, due_at], "preview_")
            if job_id in seen_ids:
                warn("duplicate_system_time")
                continue
            if len(jobs) >= 10000:
                raise ValueError("Preview exceeds the supported schedule size")
            seen_ids.add(job_id)
            jobs.append({
                "preview_job_id": job_id, "row_reference": row_id,
                "preview_device_id": devices[name]["preview_device_id"],
                "system_reference": _reference(system_name, "system_"),
                "engine": engine, "platform": platform, "count": count,
                "intro_album_reference": _reference(intro, "album_") if intro else None,
                "album_reference": _reference(selected_album, "album_"),
                "page_reference": _reference([row.get("page"), row.get("page_name")], "page_")
                    if row.get("page") or row.get("page_name") else None,
                "base_time": base_time, "effective_local_time": local.strftime("%H:%M"),
                "due_at": due_at, "dry_run": True,
            })
    warnings.extend({"code": code, "count": count} for code, count in sorted(warning_counts.items()))
    warnings.append({"code": "album_contents_and_publication_unverified", "count": 1})
    jobs.sort(key=lambda job: (job["due_at"], job["preview_job_id"]))
    return {
        "dry_run": True, "activation_allowed": False, "plans_created": 0,
        "reference_date": day.isoformat(), "timezone": timezone_name,
        "stats": {"profiles": len(profiles), "enabled_devices": len(devices),
                  "disabled_devices": disabled, "systems": len(systems),
                  "matrix_rows": len(rows), "albums": len(albums), "preview_jobs": len(jobs)},
        "devices": list(devices.values()), "jobs": jobs, "warnings": warnings,
    }
