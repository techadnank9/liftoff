"""Check every model in llm.MODELS exists on this Crusoe account.

    python scripts/check_models.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from liftoff import llm  # noqa: E402

available = llm.list_models()
print(f"{len(available)} models on this account:")
for m in available:
    print("  ", m)
missing = sorted({m for m in llm.MODELS.values() if m not in available})
print()
for role, model in llm.MODELS.items():
    print(f"{'ok ' if model in available else 'MISSING'} {role:16} {model}")
if missing:
    print("\nFix these names in llm.MODELS:", missing)
    sys.exit(1)
print("\nAll role models found.")
