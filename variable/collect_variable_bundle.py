import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import re
import shutil
import time
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

"""
collect_variable_bundle.py
--------------------------
But:
- Tu colles une variable/texte à chercher
- Le script scanne le projet et trouve les fichiers qui contiennent cette variable
- Si nb_fichiers >= THRESHOLD_TXT (par défaut 7):
      -> il génère un fichier TXT unique avec le contenu de tous les fichiers trouvés
- Sinon (< THRESHOLD_TXT):
      -> il COPIE les fichiers trouvés dans tools\\variable\\collected\\ (structure conservée)

IMPORTANT:
- À chaque exécution, le dossier tools\\variable est vidé AVANT (sauf les scripts .py présents à la racine du dossier tools\\variable).
- AUCUN ZIP ici.
"""

# =========================================================
# CONFIG
# =========================================================
PROJECT_ROOT_DEFAULT = r"C:\Users\Dropbox\Jerry Kamgang\Softwares\Scripts\Jk_Scripts\JK Tools\SendFX"
OUT_ROOT_DEFAULT = r"C:\Users\Dropbox\Jerry Kamgang\Softwares\Scripts\Jk_Scripts\JK Tools\SendFX\tools\variable"

OUT_COPY_DIRNAME = "collected"
OUT_TXT_FILENAME = "EXPORT_VARIABLE_MATCHES_FOR_CHATGPT.txt"

# Seuil: si >= ce nombre de fichiers matchés => export TXT, sinon copie fichiers
THRESHOLD_TXT = 7

# Limites export TXT
MAX_BYTES_PER_FILE = 500_000        # limite par fichier (texte tronqué au-delà)
MAX_TOTAL_OUTPUT_BYTES = 12_000_000 # limite totale (12MB)
MAX_DEPTH = 80

# Dossiers/fichiers à ignorer au scan
IGNORE_DIRS = {
    ".venv", "venv", "env",
    "__pycache__", ".pytest_cache",
    ".git", ".idea", ".vscode",
    "node_modules",
    "dist", "build",
    OUT_COPY_DIRNAME,
    "zip",  # au cas où
}
IGNORE_FILES = {"pyvenv.cfg", "CACHEDIR.TAG"}

# Extensions à scanner (tu peux élargir)
SCAN_EXTS = {
    ".py", ".txt", ".md", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".env",
    ".sql",
    ".html", ".css", ".js",
    ".ts", ".tsx", ".jsx",
    ".dart",
    ".bat", ".ps1", ".sh",
}


# =========================================================
# HELPERS
# =========================================================
def is_ignored_dir(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(d.lower() in parts for d in IGNORE_DIRS)

def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False

def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")
    except Exception:
        return ""

def clear_directory(dir_path: Path, *, keep_paths: set[Path] | None = None) -> None:
    """
    Vide un dossier (supprime tout), en gardant éventuellement certains paths absolus.
    """
    keep_paths = {p.resolve() for p in (keep_paths or set())}

    if not dir_path.exists():
        return

    for item in dir_path.iterdir():
        try:
            if item.resolve() in keep_paths:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception:
            pass

def collect_keep_paths_for_out_root(out_root: Path) -> set[Path]:
    """
    Conserve tous les .py à la racine de tools\\variable
    (donc tes scripts moteurs ne seront jamais supprimés).
    """
    keep: set[Path] = set()
    if not out_root.exists():
        return keep
    for p in out_root.iterdir():
        if p.is_file() and p.suffix.lower() == ".py":
            keep.add(p.resolve())
    return keep

def find_files_containing(project_root: Path, needle: str, mode: str, ignore_roots: list[Path] | None = None) -> list[Path]:
    needle = (needle or "").strip()
    if not needle:
        return []

    ignore_roots = [r for r in (ignore_roots or []) if isinstance(r, Path)]

    if mode == "literal":
        matcher = lambda s: needle in s
    elif mode == "word":
        pattern = re.compile(rf"\b{re.escape(needle)}\b")
        matcher = lambda s: bool(pattern.search(s))
    else:  # regex
        try:
            pattern = re.compile(needle)
        except re.error:
            raise ValueError("Regex invalide. Corrige ta regex ou choisis 'Literal'.")
        matcher = lambda s: bool(pattern.search(s))

    hits: list[Path] = []
    for root, dirs, files in os.walk(project_root):
        root_path = Path(root)

        # ignore roots (ex: tools\variable) pour éviter recursion
        if any(is_under(root_path, ir) for ir in ignore_roots):
            dirs[:] = []
            continue

        dirs[:] = [d for d in dirs if not is_ignored_dir(root_path / d)]
        if is_ignored_dir(root_path):
            continue

        for fn in files:
            p = root_path / fn
            if fn in IGNORE_FILES:
                continue
            if p.suffix.lower() not in SCAN_EXTS:
                continue

            content = safe_read_text(p)
            if content and matcher(content):
                hits.append(p)

    # tri stable
    hits.sort(key=lambda x: str(x).lower())
    return hits

def copy_hits(project_root: Path, hits: list[Path], out_copy_root: Path) -> int:
    copied = 0
    for src in hits:
        try:
            rel = src.relative_to(project_root)
        except Exception:
            rel = Path("_external") / src.name

        dest = out_copy_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    return copied


# =========================================================
# TXT EXPORT (contenu de tous les fichiers matchés)
# =========================================================
def export_matches_to_txt(
    project_root: Path,
    out_root: Path,
    hits: list[Path],
    needle: str,
    mode: str,
    output_filename: str = OUT_TXT_FILENAME,
) -> Path:
    out_path = (out_root / output_filename).resolve()

    # Exclure le fichier output de lecture (si re-run)
    hits = [p for p in hits if p.resolve() != out_path]

    written_bytes = 0
    now_ts = time.time()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def write_line(f, s: str):
        nonlocal written_bytes
        data = (s + "\n").encode("utf-8", errors="replace")
        if written_bytes + len(data) > MAX_TOTAL_OUTPUT_BYTES:
            tail = "\n<<OUTPUT TRUNCATED: MAX_TOTAL_OUTPUT_BYTES reached>>\n"
            f.write(tail)
            raise StopIteration
        f.write(s + "\n")
        written_bytes += len(data)

    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        write_line(f, "EXPORT FOR CHATGPT — VARIABLE MATCHES (FILES + CONTENTS)")
        write_line(f, f"ROOT: {project_root}")
        write_line(f, f"GENERATED_AT: {ts}")
        write_line(f, f"NEEDLE: {needle!r}")
        write_line(f, f"MODE: {mode}")
        write_line(f, f"HITS: {len(hits)}")
        write_line(f, f"THRESHOLD_TXT: {THRESHOLD_TXT}")
        write_line(f, f"MAX_BYTES_PER_FILE: {MAX_BYTES_PER_FILE}")
        write_line(f, f"MAX_TOTAL_OUTPUT_BYTES: {MAX_TOTAL_OUTPUT_BYTES}")
        write_line(f, "=" * 140)
        write_line(f, "")

        try:
            for p in hits:
                rel = None
                try:
                    rel = p.relative_to(project_root)
                except Exception:
                    rel = p

                write_line(f, "\n" + "#" * 140)
                write_line(f, f"FILE: {p.name}")
                write_line(f, f"PATH: {p}")
                write_line(f, f"RELATIVE: {rel}")
                try:
                    size = p.stat().st_size
                except Exception:
                    size = -1
                write_line(f, f"SIZE_BYTES: {size}")
                write_line(f, "#" * 140)

                raw = safe_read_text(p)
                raw_bytes = raw.encode("utf-8", errors="replace")
                if len(raw_bytes) > MAX_BYTES_PER_FILE:
                    truncated = raw_bytes[:MAX_BYTES_PER_FILE].decode("utf-8", errors="replace")
                    write_line(f, truncated)
                    write_line(f, "\n<<FILE TRUNCATED: MAX_BYTES_PER_FILE reached>>")
                else:
                    write_line(f, raw)

                write_line(f, "")

        except StopIteration:
            pass

    return out_path


# =========================================================
# PIPELINE
# =========================================================
def run_bundle(project_root: Path, out_root: Path, needle: str, mode: str) -> dict:
    out_root.mkdir(parents=True, exist_ok=True)

    # 1) purge tools\variable en gardant les scripts .py à la racine
    keep = collect_keep_paths_for_out_root(out_root)
    clear_directory(out_root, keep_paths=keep)

    # 2) re-créer collected (au cas où)
    out_copy_root = out_root / OUT_COPY_DIRNAME
    out_copy_root.mkdir(parents=True, exist_ok=True)

    # 3) scan
    hits = find_files_containing(project_root, needle, mode, ignore_roots=[out_root])

    result = {
        "needle": needle,
        "mode": mode,
        "hits": len(hits),
        "action": "",
        "copy_dir": "",
        "txt_path": "",
    }

    # 4) condition: TXT ou copie
    if len(hits) >= THRESHOLD_TXT:
        txt_path = export_matches_to_txt(project_root, out_root, hits, needle, mode, OUT_TXT_FILENAME)
        result["action"] = "txt"
        result["txt_path"] = str(txt_path)
    else:
        copied = copy_hits(project_root, hits, out_copy_root) if hits else 0
        result["action"] = "copy"
        result["copy_dir"] = str(out_copy_root)
        result["copied"] = copied

    return result


# =========================================================
# UI (Tkinter)
# =========================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SendFX • Variable Bundle (Copy or TXT)")
        self.geometry("900x560")
        self.minsize(860, 520)

        self.project_root = tk.StringVar(value=PROJECT_ROOT_DEFAULT)
        self.out_root = tk.StringVar(value=OUT_ROOT_DEFAULT)
        self.needle = tk.StringVar(value="")
        self.mode = tk.StringVar(value="literal")  # literal | word | regex
        self.threshold = tk.IntVar(value=THRESHOLD_TXT)

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 8}
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, **pad)

        # Project root
        r1 = ttk.Frame(frm); r1.pack(fill="x")
        ttk.Label(r1, text="Dossier projet (à scanner) :").pack(side="left")
        ttk.Entry(r1, textvariable=self.project_root).pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(r1, text="Choisir…", command=self._pick_project).pack(side="left")

        # Output root
        r2 = ttk.Frame(frm); r2.pack(fill="x", pady=(6, 0))
        ttk.Label(r2, text="Dossier sortie (tools\\variable) :").pack(side="left")
        ttk.Entry(r2, textvariable=self.out_root).pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(r2, text="Choisir…", command=self._pick_out).pack(side="left")

        # Needle
        r3 = ttk.Frame(frm); r3.pack(fill="x", pady=(14, 0))
        ttk.Label(r3, text="Variable / texte à chercher :").pack(side="left")
        ttk.Entry(r3, textvariable=self.needle).pack(side="left", fill="x", expand=True, padx=10)

        # Mode
        r4 = ttk.Frame(frm); r4.pack(fill="x", pady=(6, 0))
        ttk.Label(r4, text="Mode :").pack(side="left")
        ttk.Radiobutton(r4, text="Literal", variable=self.mode, value="literal").pack(side="left", padx=8)
        ttk.Radiobutton(r4, text="Mot complet", variable=self.mode, value="word").pack(side="left", padx=8)
        ttk.Radiobutton(r4, text="Regex", variable=self.mode, value="regex").pack(side="left", padx=8)

        # Threshold
        r5 = ttk.Frame(frm); r5.pack(fill="x", pady=(6, 0))
        ttk.Label(r5, text="Seuil export TXT (>=) :").pack(side="left")
        ttk.Spinbox(r5, from_=1, to=999, textvariable=self.threshold, width=6).pack(side="left", padx=8)
        ttk.Label(r5, text="(si hits >= seuil => TXT, sinon copie fichiers)").pack(side="left")

        # Buttons
        r6 = ttk.Frame(frm); r6.pack(fill="x", pady=(14, 0))
        ttk.Button(r6, text="Lancer", command=self._run).pack(side="left")
        ttk.Button(r6, text="Ouvrir dossier sortie", command=self._open_out).pack(side="left", padx=10)

        # Log
        ttk.Label(frm, text="Log :").pack(anchor="w", pady=(16, 6))
        self.log = tk.Text(frm, height=16, wrap="word")
        self.log.pack(fill="both", expand=True)

        help_txt = (
            "Règle:\n"
            f"- Si nombre de fichiers trouvés >= seuil (par défaut {THRESHOLD_TXT}) => export TXT unique.\n"
            f"- Sinon => copie des fichiers dans '{OUT_COPY_DIRNAME}\\' (structure conservée).\n"
            "\nImportant:\n"
            "- À chaque run, tools\\variable est vidé en premier (sauf scripts .py à la racine).\n"
            "- AUCUN ZIP.\n"
        )
        self.log.insert("end", help_txt + "\n\n")

    def _pick_project(self):
        d = filedialog.askdirectory(title="Choisir le dossier du projet")
        if d:
            self.project_root.set(d)

    def _pick_out(self):
        d = filedialog.askdirectory(title="Choisir le dossier de sortie (tools\\variable)")
        if d:
            self.out_root.set(d)

    def _open_out(self):
        outp = Path(self.out_root.get().strip())
        if not outp.exists():
            messagebox.showwarning("Dossier introuvable", f"Ce dossier n'existe pas:\n{outp}")
            return
        os.startfile(str(outp))

    def _append(self, s: str):
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.update_idletasks()

    def _run(self):
        project_root = Path(self.project_root.get().strip())
        out_root = Path(self.out_root.get().strip())
        needle = self.needle.get().strip()
        mode = self.mode.get().strip()

        global THRESHOLD_TXT
        try:
            THRESHOLD_TXT = int(self.threshold.get())
        except Exception:
            THRESHOLD_TXT = 7

        if not project_root.exists():
            messagebox.showerror("Erreur", f"Dossier projet introuvable:\n{project_root}")
            return

        try:
            out_root.mkdir(parents=True, exist_ok=True)
        except Exception:
            messagebox.showerror("Erreur", f"Impossible de créer le dossier sortie:\n{out_root}")
            return

        if not needle:
            messagebox.showwarning("Info", "Colle une variable/texte à chercher.")
            return

        self._append("-" * 60)
        self._append(f"Projet : {project_root}")
        self._append(f"Sortie : {out_root}")
        self._append(f"Recherche : {needle!r} | mode={mode} | seuil={THRESHOLD_TXT}")
        self._append("Purge tools\\variable puis scan...")

        try:
            res = run_bundle(project_root, out_root, needle, mode)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            self._append(f"ERREUR: {e}")
            return

        self._append(f"Fichiers trouvés: {res['hits']}")

        if res["action"] == "txt":
            self._append("Action: EXPORT TXT ✅")
            self._append(f"TXT: {res['txt_path']}")
            messagebox.showinfo("Terminé", f"✅ Export TXT généré:\n{res['txt_path']}")
        else:
            self._append("Action: COPIE fichiers ✅")
            self._append(f"Dossier: {res['copy_dir']}")
            self._append(f"Copiés: {res.get('copied', 0)}")
            messagebox.showinfo("Terminé", f"✅ Fichiers copiés dans:\n{res['copy_dir']}")

        self._append("OK ✅")


if __name__ == "__main__":
    App().mainloop()
