import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Lancer l'app UI
import ui.app  # si ui/app.py exécute l'UI au moment de l'import
