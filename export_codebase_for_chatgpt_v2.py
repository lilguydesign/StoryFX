import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import time
from pathlib import Path
from datetime import datetime


# ============================================================================
# MODE D'EXECUTION
#   - "headless" : exécution automatique (par défaut)
#   - "ui"       : interface Tkinter (optionnel)
# ============================================================================
RUN_MODE = "headless"


# -----------------------------
# Ignorer dossiers bruit
# -----------------------------
IGNORE_DIRS = {
    ".venv", "venv", "env",
    "__pycache__",
    ".git", ".idea", ".pytest_cache",
    "node_modules",
    "dist", "build",
}

IGNORE_FILES = {"pyvenv.cfg", "CACHEDIR.TAG"}

# -----------------------------
# Réglages limites
# -----------------------------
MAX_BYTES_PER_FILE = 500_000        # limite par fichier (py OU non-py inclus)
MAX_TOTAL_OUTPUT_BYTES = 12_000_000 # limite totale export (12 MB)
MAX_DEPTH = 50

# Extensions utiles (inclure sans contenu CSV)
DEFAULT_INCLUDE_EXTS = [
    # Code
    ".dart", ".js", ".ts", ".py",
    ".html", ".css",

    # Config / data textuelle
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",

    # Docs / prompts IA
    ".md", ".txt", ".prompt",

    # Shell / scripts
    ".sh", ".bat", ".ps1",

    # SQL
    ".sql",
]

# Extensions à exclure (cache, volumineux, inutiles pour code)
DEFAULT_EXCLUDE_EXTS = [
    # Data lourde
    ".csv", ".parquet",

    # Images
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",

    # Vidéos / audio
    ".mp4", ".mov", ".avi", ".mp3", ".wav",

    # Binaires
    ".exe", ".dll", ".so", ".dylib",

    # Archives
    ".zip", ".rar", ".7z",
]


# ============================================================================
# VERSIONING DU RENDU
#   - Stocke un compteur dans: <root>/.export_version.txt
#   - Chaque run:
#       1) lit la version actuelle
#       2) calcule la suivante (increment)
#       3) écrit la version suivante sur disque
#       4) supprime l'ancien fichier rendu
#       5) regénère un nouveau rendu avec la version dans l'en-tête
# ============================================================================
VERSION_FILE_NAME = ".export_version.txt"


def _read_int(path: Path) -> int:
    try:
        raw = (path.read_text(encoding="utf-8") or "").strip()
        if not raw:
            return 0
        # accepte "1", "001", "v001", ".001", etc.
        raw = raw.lower().replace("v", "").replace(".", "").strip()
        return int(raw)
    except Exception:
        return 0


def _write_int(path: Path, n: int) -> None:
    path.write_text(str(n), encoding="utf-8", newline="\n")


def next_version_and_cleanup(root: Path, output_filename: str) -> tuple[str, int, Path]:
    """
    Retourne:
      - version_str: '.000', '.001', ...
      - version_int
      - out_path (chemin du rendu)

    Comportement demandé:
      - incrémente d'abord ce qu'il lit
      - ensuite supprime le fichier rendu (si existe)
      - ensuite génère
    """
    root = root.resolve()
    ver_path = (root / VERSION_FILE_NAME).resolve()
    out_path = (root / output_filename).resolve()

    current = _read_int(ver_path)
    new_version_int = current + 1
    _write_int(ver_path, new_version_int)

    # Suppression explicite du rendu précédent (même si 'w' overwrite déjà)
    try:
        if out_path.exists() and out_path.is_file():
            out_path.unlink()
    except Exception:
        # on ne bloque pas l'export si suppression impossible (ex: fichier ouvert)
        pass

    version_str = f".{new_version_int:03d}"  # .000, .001, .002, ...
    return version_str, new_version_int, out_path


# ============================================================================
# EXPORT CORE
# ============================================================================
def is_ai_related_file(path: Path) -> bool:
    name = path.name.lower()
    keywords = [
        "gpt", "openai", "dalle", "prompt",
        "llm", "chat", "ai", "assistant"
    ]
    return any(k in name for k in keywords)


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")


def export_codebase(
    root_folder: str,
    include_subdirs: bool,
    modified_only: bool,
    modified_hours: int,
    include_exts: list[str],
    exclude_exts: list[str],
    output_filename: str = "EXPORT_CODEBASE_FOR_CHATGPT.txt",
    version_str: str | None = None,
) -> str:
    root = Path(root_folder).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Dossier introuvable: {root}")

    # --- Output path (à exclure) ---
    out_path = (root / output_filename).resolve()

    # --- Script actuel (à exclure) ---
    try:
        current_script = Path(__file__).resolve()
    except Exception:
        current_script = None

    written_bytes = 0

    now_ts = time.time()
    cutoff_ts = now_ts - (modified_hours * 3600)

    def write_line(f, s: str):
        nonlocal written_bytes
        data = (s + "\n").encode("utf-8", errors="replace")
        if written_bytes + len(data) > MAX_TOTAL_OUTPUT_BYTES:
            tail = "\n<<OUTPUT TRUNCATED: MAX_TOTAL_OUTPUT_BYTES reached>>\n"
            f.write(tail)
            raise StopIteration
        f.write(s + "\n")
        written_bytes += len(data)

    def should_ignore_dir(name: str) -> bool:
        return name in IGNORE_DIRS

    def should_ignore_file_by_name(name: str) -> bool:
        if name in IGNORE_FILES:
            return True
        # ✅ exclure tout ce qui contient "chatgpt" dans le nom
        if "chatgpt" in name.lower():
            return True
        return False

    def should_ignore_file_by_path(path: Path) -> bool:
        # ✅ exclure le fichier output
        try:
            if path.resolve() == out_path:
                return True
        except Exception:
            pass

        # ✅ exclure le script actuel
        if current_script is not None:
            try:
                if path.resolve() == current_script:
                    return True
            except Exception:
                pass

        return False

    def allowed_by_ext(path: Path) -> bool:
        ext = path.suffix.lower()

        ex = {e.lower() for e in exclude_exts}
        inc = {e.lower() for e in include_exts}

        if ext in ex:
            return False

        # ⚠️ NOTE: ton commentaire disait "Toujours inclure IA",
        # mais ton script exclut aussi "chatgpt" via should_ignore_file_by_name.
        # On conserve ton comportement actuel (anti-recursion).
        if is_ai_related_file(path):
            return True

        if not include_exts:
            return True

        return ext in inc

    def allowed_by_time(path: Path) -> bool:
        if not modified_only:
            return True
        try:
            mtime = path.stat().st_mtime
        except Exception:
            return False
        return mtime >= cutoff_ts

    def iter_dirs():
        if include_subdirs:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not should_ignore_dir(d)]
                yield Path(dirpath), sorted(dirnames), sorted(filenames)
        else:
            dirpath = root
            dirnames = [d.name for d in dirpath.iterdir() if d.is_dir() and not should_ignore_dir(d.name)]
            filenames = [p.name for p in dirpath.iterdir() if p.is_file()]
            yield dirpath, sorted(dirnames), sorted(filenames)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    v = version_str or ""

    # (re)création du fichier rendu
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        # Header
        write_line(f, "EXPORT FOR CHATGPT — TREE + CODE CONTENTS")
        write_line(f, f"VERSION: {v}" if v else "VERSION: (none)")
        write_line(f, f"ROOT: {root}")
        write_line(f, f"GENERATED_AT: {ts}")
        write_line(f, f"INCLUDE_SUBDIRS: {include_subdirs}")
        write_line(f, f"MAX_DEPTH: {MAX_DEPTH}")
        write_line(f, f"MAX_BYTES_PER_FILE: {MAX_BYTES_PER_FILE}")
        write_line(f, f"MAX_TOTAL_OUTPUT_BYTES: {MAX_TOTAL_OUTPUT_BYTES}")
        write_line(f, f"MODIFIED_ONLY: {modified_only}")
        if modified_only:
            write_line(f, f"MODIFIED_HOURS: {modified_hours} (cutoff: {datetime.fromtimestamp(cutoff_ts)})")
        write_line(f, f"INCLUDE_EXTS: {include_exts if include_exts else 'ALL (except excluded)'}")
        write_line(f, f"EXCLUDE_EXTS: {exclude_exts}")
        write_line(f, f"EXCLUDED_SPECIAL: current script + output file + any name containing 'chatgpt'")
        write_line(f, "=" * 140)
        write_line(f, "")

        try:
            for dirpath, dirnames, filenames in iter_dirs():
                rel = os.path.relpath(dirpath, root)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                if depth > MAX_DEPTH:
                    continue

                write_line(f, "#" * 140)
                write_line(f, f"SCAN DIR: {dirpath}")
                write_line(f, f"RELATIVE: {rel}")
                write_line(f, "#" * 140)

                if dirnames:
                    write_line(f, "SUBDIRS:")
                    for d in dirnames:
                        write_line(f, f"  📁 {d}/")
                else:
                    write_line(f, "SUBDIRS: (none)")

                # Fichiers listés
                write_line(f, "\nFILES:")
                any_file = False
                files_in_dir: list[Path] = []

                for fn in filenames:
                    if should_ignore_file_by_name(fn):
                        continue

                    fp = dirpath / fn
                    if not fp.is_file():
                        continue

                    if should_ignore_file_by_path(fp):
                        continue

                    if not allowed_by_ext(fp):
                        continue

                    if not allowed_by_time(fp):
                        continue

                    any_file = True
                    files_in_dir.append(fp)

                    try:
                        size = fp.stat().st_size
                    except Exception:
                        size = -1

                    icon = "🐍" if fp.suffix.lower() == ".py" else "📄"
                    write_line(f, f"  {icon} {fn} ({size} bytes)")

                if not any_file:
                    write_line(f, "  (none)")

                # Contenu des fichiers sélectionnés dans ce dossier
                if not files_in_dir:
                    write_line(f, "\nCONTENTS: (none)")
                    write_line(f, "")
                    continue

                write_line(f, "\n" + "-" * 140)
                write_line(f, "CONTENTS (for selected files):")
                write_line(f, "-" * 140)

                for p in sorted(files_in_dir, key=lambda x: str(x).lower()):
                    write_line(f, "\n" + "=" * 140)
                    write_line(f, f"FILE: {p.name}")
                    write_line(f, f"PATH: {p}")
                    write_line(f, "=" * 140)

                    try:
                        raw = _safe_read_text(p)
                    except Exception as e:
                        write_line(f, f"<<ERROR READING FILE: {e}>>")
                        continue

                    raw_bytes = raw.encode("utf-8", errors="replace")
                    if len(raw_bytes) > MAX_BYTES_PER_FILE:
                        truncated = raw_bytes[:MAX_BYTES_PER_FILE].decode("utf-8", errors="replace")
                        write_line(f, truncated)
                        write_line(f, "\n<<FILE TRUNCATED: MAX_BYTES_PER_FILE reached>>")
                    else:
                        write_line(f, raw)

                write_line(f, "\n")

        except StopIteration:
            pass

    return str(out_path)


# ============================================================================
# RUNNERS
# ============================================================================
def run_headless() -> int:
    root = Path(__file__).resolve().parent
    output_name = "EXPORT_CODEBASE_FOR_CHATGPT.txt"

    version_str, version_int, out_path = next_version_and_cleanup(root, output_name)

    print("🚀 Export automatique (headless)")
    print(f"📁 Root       : {root}")
    print(f"🧾 Version    : {version_str} (#{version_int})")
    print(f"📄 Output     : {out_path.name}")
    print("🧹 Ancien rendu supprimé (si existait), génération en cours...")

    try:
        out = export_codebase(
            root_folder=str(root),
            include_subdirs=True,
            modified_only=False,
            modified_hours=48,
            include_exts=DEFAULT_INCLUDE_EXTS,
            exclude_exts=DEFAULT_EXCLUDE_EXTS,
            output_filename=output_name,
            version_str=version_str,
        )
        print(f"✅ Terminé: {out}")
        return 0
    except Exception as e:
        print("❌ Erreur durant l’export")
        print(str(e))
        return 1


def run_ui() -> None:
    # Import Tkinter uniquement si on en a besoin (évite problèmes headless)
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Export Codebase for ChatGPT")
            self.geometry("820x520")

            self.folder_var = tk.StringVar(value=str(Path(__file__).resolve().parent))
            self.subdirs_var = tk.BooleanVar(value=True)

            self.modified_only_var = tk.BooleanVar(value=False)
            self.hours_var = tk.IntVar(value=48)

            self.include_exts_var = tk.StringVar(value=", ".join(DEFAULT_INCLUDE_EXTS))
            self.exclude_exts_var = tk.StringVar(value=", ".join(DEFAULT_EXCLUDE_EXTS))

            self.output_name_var = tk.StringVar(value="EXPORT_CODEBASE_FOR_CHATGPT.txt")

            self._build()

        def _build(self):
            pad = {"padx": 10, "pady": 6}

            frm = ttk.Frame(self)
            frm.pack(fill="both", expand=True, **pad)

            # Folder picker
            row1 = ttk.Frame(frm)
            row1.pack(fill="x", **pad)
            ttk.Label(row1, text="Dossier racine:").pack(side="left")
            ttk.Entry(row1, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=8)
            ttk.Button(row1, text="Choisir...", command=self.pick_folder).pack(side="left")

            # Options
            row2 = ttk.Frame(frm)
            row2.pack(fill="x", **pad)
            ttk.Checkbutton(row2, text="Inclure sous-dossiers (scan récursif)", variable=self.subdirs_var).pack(side="left")

            row3 = ttk.Frame(frm)
            row3.pack(fill="x", **pad)
            ttk.Checkbutton(
                row3,
                text="Exporter seulement les fichiers modifiés récemment",
                variable=self.modified_only_var,
                command=self.toggle_hours
            ).pack(side="left")

            ttk.Label(row3, text="Heures:").pack(side="left", padx=(20, 6))
            self.hours_spin = ttk.Spinbox(row3, from_=1, to=720, textvariable=self.hours_var, width=6)
            self.hours_spin.pack(side="left")
            ttk.Label(row3, text="(ex: 24, 48, 72)").pack(side="left", padx=6)

            # Extensions
            row4 = ttk.Frame(frm)
            row4.pack(fill="x", **pad)
            ttk.Label(row4, text="Inclure extensions (séparées par virgule):").pack(anchor="w")
            ttk.Entry(row4, textvariable=self.include_exts_var).pack(fill="x")

            row5 = ttk.Frame(frm)
            row5.pack(fill="x", **pad)
            ttk.Label(row5, text="Exclure extensions (séparées par virgule):").pack(anchor="w")
            ttk.Entry(row5, textvariable=self.exclude_exts_var).pack(fill="x")

            # Output
            row6 = ttk.Frame(frm)
            row6.pack(fill="x", **pad)
            ttk.Label(row6, text="Nom du fichier export (créé à la racine):").pack(anchor="w")
            ttk.Entry(row6, textvariable=self.output_name_var).pack(fill="x")

            # Buttons
            row7 = ttk.Frame(frm)
            row7.pack(fill="x", **pad)
            ttk.Button(row7, text="Exporter", command=self.run_export).pack(side="left")
            ttk.Button(row7, text="Fermer", command=self.destroy).pack(side="right")

            # Status box
            self.status = tk.Text(frm, height=10)
            self.status.pack(fill="both", expand=True, **pad)
            self.status.insert("end", "Prêt.\n")

            self.toggle_hours()

        def pick_folder(self):
            chosen = filedialog.askdirectory(initialdir=self.folder_var.get())
            if chosen:
                self.folder_var.set(chosen)

        def toggle_hours(self):
            state = "normal" if self.modified_only_var.get() else "disabled"
            self.hours_spin.configure(state=state)

        def log(self, msg: str):
            self.status.insert("end", msg + "\n")
            self.status.see("end")
            self.update_idletasks()

        def run_export(self):
            try:
                root_folder = self.folder_var.get().strip().strip('"')
                root = Path(root_folder).expanduser().resolve()

                include_subdirs = bool(self.subdirs_var.get())
                modified_only = bool(self.modified_only_var.get())
                hours = int(self.hours_var.get())

                include_exts = [e.strip().lower() for e in self.include_exts_var.get().split(",") if e.strip()]
                exclude_exts = [e.strip().lower() for e in self.exclude_exts_var.get().split(",") if e.strip()]

                output_name = self.output_name_var.get().strip() or "EXPORT_CODEBASE_FOR_CHATGPT.txt"

                version_str, version_int, _ = next_version_and_cleanup(root, output_name)

                self.log(f"🧾 Version: {version_str} (#{version_int})")
                self.log("🧹 Ancien rendu supprimé (si existait)")
                self.log("Export en cours...")

                out = export_codebase(
                    root_folder=str(root),
                    include_subdirs=include_subdirs,
                    modified_only=modified_only,
                    modified_hours=hours,
                    include_exts=include_exts,
                    exclude_exts=exclude_exts,
                    output_filename=output_name,
                    version_str=version_str,
                )
                self.log(f"✅ Export terminé: {out}")
                messagebox.showinfo("Export terminé", f"Fichier créé:\n{out}\nVersion: {version_str}")

            except Exception as e:
                self.log(f"❌ Erreur: {e}")
                messagebox.showerror("Erreur", str(e))

    App().mainloop()


if __name__ == "__main__":
    if RUN_MODE.lower().strip() == "ui":
        run_ui()
    else:
        raise SystemExit(run_headless())
