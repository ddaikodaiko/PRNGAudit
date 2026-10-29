# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

VECTORS_DIR = Path(__file__).parent / "vectors" / "data"


def load_vectors(name: str) -> dict[str, Any]:
    """Carga un fichero de vectores de referencia generado por `tests/vectors/generate.sh`."""
    path = VECTORS_DIR / name
    if not path.exists():
        pytest.fail(f"faltan los vectores {path}; ejecuta tests/vectors/generate.sh")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
