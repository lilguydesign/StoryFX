import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
from collections import Counter, defaultdict

# ❌ Dossiers à ignorer (environnements & bruit)
IGNORE_DIRS = {
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".git",
    ".idea",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
}

# (optionnel) fichiers à ignorer
IGNORE_FILES = {
    "pyvenv.cfg",
    "CACHEDIR.TAG",
}


def _ext_of(filename: str) -> str:
    """Retourne l'extension normalisée (ex: '.py') ou '(no_ext)'."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower().strip()
    return ext if ext else "(no_ext)"


def print_tree(root: str, max_depth: int = 50):
    root = os.path.abspath(root)
    print(f"📁 {os.path.basename(root)}/")

    # --- Stats globales ---
    python_files: list[str] = []
    other_files: list[str] = []
    ext_counter: Counter[str] = Counter()
    total_files = 0
    total_dirs = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # 🔥 filtrage des dossiers AVANT descente récursive
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1

        if depth > max_depth:
            dirnames[:] = []
            continue

        indent = "  " * depth

        # ne pas ré-afficher la racine
        if depth > 0:
            print(f"{indent}📁 {os.path.basename(dirpath)}/")
            total_dirs += 1  # ✅ on compte ce dossier (sous-dossier)
        else:
            # ✅ racine comptée comme dossier aussi
            total_dirs += 1

        dirnames.sort()
        filenames.sort()

        for fn in filenames:
            if fn in IGNORE_FILES:
                continue

            fp = os.path.join(dirpath, fn)

            # Taille fichier (optionnel, comme avant)
            try:
                size = os.path.getsize(fp)
            except Exception:
                size = -1

            print(f"{indent}  📄 {fn} ({size} bytes)")

            # --- Stats fichiers ---
            total_files += 1
            rel_fp = os.path.relpath(fp, root)  # chemin relatif pour le rapport
            ext = _ext_of(fn)
            ext_counter[ext] += 1

            if ext == ".py":
                python_files.append(rel_fp)
            else:
                other_files.append(rel_fp)

    # --- Rapport final ---
    print("\n" + "=" * 60)
    print("📌 RAPPORT FINAL")
    print("=" * 60)

    print(f"📂 Total dossiers : {total_dirs}")
    print(f"📄 Total fichiers : {total_files}")

    print("\n🐍 Fichiers Python (.py) :")
    if python_files:
        for p in python_files:
            print(f"  - {p}")
    else:
        print("  (aucun)")

    print("\n🧩 Autres fichiers (non .py) :")
    if other_files:
        for p in other_files:
            print(f"  - {p}")
    else:
        print("  (aucun)")

    # Bonus : résumé par extension (très pratique)
    print("\n📊 Répartition par extension :")
    for ext, cnt in sorted(ext_counter.items(), key=lambda x: (-x[1], x[0])):
        print(f"  - {ext}: {cnt}")

    print("=" * 60)


if __name__ == "__main__":
    # ✅ Toujours le dossier où se trouve le script (ex: SendFX)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print_tree(script_dir, max_depth=50)
