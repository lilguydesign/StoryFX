# -*- coding: utf-8 -*-
"""
Runner CLI — lance un engine (intro | multi | intro_multi)
Avec support complet :
- Facebook (pays + page_name)
- Instagram
- TikTok
- WhatsApp
"""

import json, time
import argparse
from pathlib import Path

from engine import engine_intro, engine_multi

from datetime import datetime
import os

def get_display_time() -> str:
    """Heure à afficher dans les logs (rattrapage ou réelle)."""
    t = os.environ.get("STORYFX_TIME")
    if t:
        return t
    return datetime.now().strftime("%H:%M:%S")

def log_run_header(label):
    now = get_display_time()   # au lieu de datetime.now().strftime(...)
    print("")
    print(
        f"[StoryFX] [RUN] {now} | Device = {args.profile} | "
        f"engine = {args.engine} | platform = {args.platform} | step = {label}"
    )


# ---------- Utils ----------
def load_json(path: str | Path):
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def die(msg: str, code: int = 2):
    print(f"[runner] {msg}")
    raise SystemExit(code)

def run_with_retries(label, fn, max_attempts=5):
    """
    Exécute fn() avec retries :
    - jusqu’à max_attempts tentatives
    - délais progressifs : 5s, 10s, 20s, 40s, 80s
    - NE RELANCE PAS l’exception à la fin : retourne juste 1 en cas d’échec.
    """
    global args  # ⬅️ OBLIGATOIRE pour utiliser args.profile / args.engine / args.platform

    last_exc = None

    for attempt in range(1, max_attempts + 1):
        # --- LOG RUN HEADER ---
        from datetime import datetime

        logical_time = os.environ.get("STORYFX_TIME")
        if logical_time:
            now = logical_time
        else:
            now = datetime.now().strftime("%H:%M:%S")

        print("")
        print(f"[StoryFX] [RUN] {now} | Device = {args.profile} | engine = {args.engine} | platform = {args.platform}")

        print(f"[StoryFX] [{label}] tentative {attempt}/{max_attempts}...")

        try:
            rc = fn()
            if rc == 0:
                print(f"[StoryFX] [{label}] OK à la tentative {attempt}.")
                return 0
            else:
                print(f"[StoryFX] [{label}] retour rc={rc} (tentative {attempt}).")
        except Exception as e:
            last_exc = e
            print(f"[StoryFX] [{label}] ERREUR à la tentative {attempt}: {e!r}")

        # Si ce n’est pas la dernière tentative → on attend (5, 10, 20, 40, 80)
        if attempt < max_attempts:
            delay = 5 * (2 ** (attempt - 1))  # 1→5s, 2→10s, 3→20s, 4→40s, 5→80s
            print(f"[StoryFX] [{label}] nouvelle tentative dans {delay} s...")
            time.sleep(delay)

    print(f"[StoryFX] [{label}] échec après {max_attempts} tentatives.")
    if last_exc:
        print(f"[StoryFX] [{label}] dernière exception : {last_exc!r}")

    # On NE relance pas l’exception → le process se termine proprement avec code 1
    return 1

# ---------- CLI ----------
def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()

    # profils.json
    ap.add_argument(
        "--profiles",
        default=str(Path(__file__).with_name("config").joinpath("profiles.json")),
        help="Chemin vers config/profiles.json",
    )
    ap.add_argument("--profile", required=True, help="Clé du profil")

    # Engines
    ap.add_argument(
        "--engine",
        choices=["intro", "multi", "intro_multi"],
        required=True,
        help="Engine à utiliser",
    )

    ap.add_argument("--album", required=True, help="Album (intro)")
    ap.add_argument("--album2", help="Album (multi pour intro_multi)")
    ap.add_argument("--count", type=int, default=11, help="Count pour multi")

    # Plateforme + options
    ap.add_argument(
        "--platform",
        choices=["WhatsApp", "Facebook", "Instagram", "TikTok"],
        default="WhatsApp",
    )
    ap.add_argument("--page", help="[Facebook] Pays (ex : Cameroun, Côte d’Ivoire)")
    ap.add_argument("--page-name", dest="page_name", help="[Facebook] Nom de la page")

    # 2 syntaxes acceptées pour page_name : --page-name et --page_name
    ap.add_argument(
        "--page_name",
        dest="page_name",
        type=str,
        help=argparse.SUPPRESS,
    )
    return ap


args = None

# ---------- Main ----------
def main():
    # print(f"[StoryFX] [{label}] tentative {attempt}/{max_attempts}...")

    global args
    args = build_argparser().parse_args()

    # --- Chargement du profil ---
    profiles = load_json(args.profiles)
    if "profiles" not in profiles:
        die("Le fichier profiles.json ne contient pas la clé 'profiles'.")

    if args.profile not in profiles["profiles"]:
        die(f"Profil introuvable : {args.profile}")

    base_profile = profiles["profiles"][args.profile]
    profile = dict(base_profile)
    profile["profile_name"] = args.profile  # mémoriser le nom du profil

    # --- Construction platform_opts ---
    platform_opts = {
        "page": args.page,          # Pays
        "page_name": args.page_name # Nom de la page
    }
    rc = 1

    # ========== ENGINE INTRO ==========
    if args.engine == "intro":

        def call_intro():
            try:
                return engine_intro.run(
                    profile,
                    args.album,
                    platform=args.platform,
                    platform_opts=platform_opts,
                )
            except TypeError:
                # Compat anciennes signatures
                return engine_intro.run(profile, args.album)

        rc = run_with_retries("intro", call_intro, max_attempts=5)

    # ========== ENGINE MULTI ==========
    elif args.engine == "multi":

        def call_multi():
            try:
                return engine_multi.run(
                    profile,
                    args.album,
                    args.count,
                    platform=args.platform,
                    platform_opts=platform_opts,
                )
            except TypeError:
                # Compat anciennes signatures
                return engine_multi.run(profile, args.album, args.count)

        rc = run_with_retries("multi", call_multi, max_attempts=5)

    # ========== ENGINE INTRO + MULTI ==========
    elif args.engine == "intro_multi":

        album_intro = args.album
        album_multi = args.album2 or args.album

        def call_intro():
            try:
                return engine_intro.run(
                    profile,
                    album_intro,
                    platform=args.platform,
                    platform_opts=platform_opts,
                )
            except TypeError:
                return engine_intro.run(profile, album_intro)

        def call_multi():
            try:
                return engine_multi.run(
                    profile,
                    album_multi,
                    args.count,
                    platform=args.platform,
                    platform_opts=platform_opts,
                )
            except TypeError:
                return engine_multi.run(profile, album_multi, args.count)

        rc_intro = run_with_retries("intro", call_intro, max_attempts=5)
        if rc_intro != 0:
            rc = rc_intro
        else:
            rc_multi = run_with_retries("multi", call_multi, max_attempts=5)
            rc = rc_multi

    print(f"[runner] Terminé avec code {rc}")
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
