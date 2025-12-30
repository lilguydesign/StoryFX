# cleanup_ig_variant.py
# python cleanup_ig_variant.py

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"

matrix_path = CONFIG / "matrix.json"
ui_state_path = ROOT / "ui_state.json"

def clean_matrix():
    if not matrix_path.exists():
        print("matrix.json introuvable.")
        return
    with matrix_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rows = data.get("rows", [])
    for row in rows:
        row.pop("ig_variant", None)  # supprime la clé si présente

    with matrix_path.open("w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)
    print("matrix.json nettoyé (ig_variant supprimé).")

def clean_ui_state():
    if not ui_state_path.exists():
        print("ui_state.json introuvable.")
        return
    with ui_state_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data.pop("ig_variant", None)

    with ui_state_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("ui_state.json nettoyé (ig_variant supprimé).")

if __name__ == "__main__":
    clean_matrix()
    clean_ui_state()
