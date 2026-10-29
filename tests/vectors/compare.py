# SPDX-License-Identifier: MIT
"""Compara dos directorios de vectores ignorando el campo `generated_with`.

Lo usa la CI: regenera los vectores con las herramientas reales (JDK, Node, C)
y comprueba que los datos coinciden con los versionados en el repositorio.
Así detectamos si una versión distinta de Java o de V8 cambia el algoritmo.

Uso: python tests/vectors/compare.py DIR_VERSIONADO DIR_REGENERADO
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    data.pop("generated_with", None)
    return data


def main(committed: Path, regenerated: Path) -> int:
    failures = 0
    for ref in sorted(committed.glob("*.json")):
        new = regenerated / ref.name
        if not new.exists():
            print(f"FALTA   {ref.name}")
            failures += 1
        elif load(ref) != load(new):
            print(f"DIFIERE {ref.name}")
            failures += 1
        else:
            print(f"OK      {ref.name}")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
