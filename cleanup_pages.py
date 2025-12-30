# python cleanup_pages.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
matrix_path = CONFIG / "matrix.json"

def migrate_pages_cm_ci():
    if not matrix_path.exists():
        print("matrix.json introuvable.")
        return

    with matrix_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rows = data.get("rows", [])
    changed = 0
    for row in rows:
        if row.get("platform") == "Facebook":
            if row.get("page") == "CM":
                row["page"] = "Cameroun"
                changed += 1
            elif row.get("page") == "CI":
                row["page"] = "Côte d'Ivoire"
                changed += 1

    with matrix_path.open("w", encoding="utf-8") as f:
        json.dump({"rows": rows}, f, ensure_ascii=False, indent=2)

    print(f"matrix.json : {changed} ligne(s) mises à jour (CM/CI → pays).")

if __name__ == "__main__":
    migrate_pages_cm_ci()
