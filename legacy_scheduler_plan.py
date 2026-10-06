"""Legacy business planning; disabled channel rows never generate a job."""
from typing import Iterator, Dict, Any, List
from legacy_scheduler_config import PROJECT_NAME, hhmm_add_offset, load_configs

def iter_jobs(profiles: dict, systems: dict, matrix: dict, albums: dict) -> Iterator[Dict[str, Any]]:
    """
    Génère toutes les programmations possibles.

    Un job contient maintenant :
      - album_intro : album d'intro (engine intro / intro+multi)
      - album_multi : album multi (engine multi / intro+multi)
      - count       : nombre d'images, dérivé de albums.json quand c'est du multi
    """
    # On prépare un dict {nom_album: config_album} pour aller vite
    albums_dict = {a.get("name"): a for a in albums.get("albums", [])}

    for dev_name, dev in profiles.get("profiles", {}).items():
        if not dev.get("enabled", True):
            continue  # 🔥 Skip ce device

        offset = int(dev.get("offset_minutes", 0))

        for row in matrix.get("rows", []):
            if row.get("device") != dev_name or not row.get("enabled", True):
                continue

            sys_key = row["system"]
            sys_conf = systems.get("systems", {}).get(sys_key)
            if sys_conf is None:
                print(f"[{PROJECT_NAME}] ⚠ Système '{sys_key}' introuvable dans systems.json.")
                continue

            # Compat : systems["systems"][key] peut être soit une liste,
            # soit un dict {"times": [...]}
            if isinstance(sys_conf, dict):
                times = sys_conf.get("times", [])
            else:
                times = sys_conf

            engine = row.get("engine") or ""
            album_intro = row.get("album")  or ""
            album_multi = row.get("album2") or ""
            raw_count   = row.get("count", 0) or 0
            platform    = row.get("platform", "WhatsApp")
            page        = row.get("page")
            page_name   = row.get("page_name")


            # --- Déterminer le count réel ---
            count = int(raw_count)
            # Pour multi et intro+multi, on essaie de prendre count_per_post de l'album multi
            if engine in ("multi", "intro+multi"):
                multi_name = album_multi or album_intro
                cfg = albums_dict.get(multi_name or "")
                if cfg:
                    c = cfg.get("count_per_post")
                    if c:
                        count = int(c)

            for base_time in times:
                t_effective = hhmm_add_offset(base_time, offset)
                yield {
                    "device": dev_name,
                    "system": sys_key,
                    "engine": engine,
                    "album_intro": album_intro,
                    "album_multi": album_multi,
                    "count": count,
                    "platform": platform,
                    "page": page,         # Pays
                    "page_name": page_name,  # Page
                    "base_time": base_time,
                    "offset_minutes": offset,
                    "time_effective": t_effective,
                }


def build_planning() -> List[List[str]]:
    """
    Construit un tableau lisible pour la GUI.
    Chaque ligne = [device, system, engine,
                    album_intro, album_multi,
                    platform, count, base_time,
                    offset, time_effective,
                    page, page_name, ig_variant]
    """
    profiles, systems, matrix, albums = load_configs()
    table: List[List[str]] = []

    for job in iter_jobs(profiles, systems, matrix, albums):
        table.append([
            job["device"],
            job["system"],
            job.get("engine") or "",
            job.get("album_intro") or "",
            job.get("album_multi") or "",
            job.get("platform") or "",
            str(job.get("count") or ""),
            job["base_time"],
            f"{job['offset_minutes']} min",
            job["time_effective"],
            job.get("page") or "",       # Pays
            job.get("page_name") or "",  # Nom de la page
        ])


    # Tri par heure effective puis device
    table.sort(key=lambda r: (r[9], r[0], r[1]))
    return table
