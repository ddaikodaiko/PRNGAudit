# SPDX-License-Identifier: MIT
"""Utilidades compartidas por los scripts de experimentos.

Cada experimento escribe en `experiments/out/<nombre>.json` (datos completos y
entorno de ejecución) y `experiments/out/<nombre>.md` (tabla resumen). La
carpeta `out/` no se versiona: se regenera con `make experiments`.
"""

from __future__ import annotations

import json
import os
import platform
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

OUT_DIR = Path(__file__).parent / "out"


def environment() -> dict[str, Any]:
    """Datos de la máquina, para que cualquier cifra de tiempo tenga contexto."""
    return {
        "fecha_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "plataforma": platform.platform(),
        "procesador": platform.processor() or platform.machine(),
        "cpus": os.cpu_count(),
    }


def fmt_int(n: float) -> str:
    """Entero con espacio como separador de miles (convención del español técnico)."""
    return f"{n:,.0f}".replace(",", " ")


def summarize(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "media": statistics.fmean(ordered),
        "mediana": statistics.median(ordered),
        "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
        "max": ordered[-1],
    }


def write_results(name: str, data: dict[str, Any], table_md: str) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    payload = {"experimento": name, "entorno": environment(), **data}
    (OUT_DIR / f"{name}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    env = payload["entorno"]
    footer = (
        f"\n\n_Generado el {env['fecha_utc']} con Python {env['python']}, "
        f"NumPy {env['numpy']}, {env['plataforma']}, {env['cpus']} CPU._\n"
    )
    (OUT_DIR / f"{name}.md").write_text(table_md + footer, encoding="utf-8")
    print(table_md + footer)
