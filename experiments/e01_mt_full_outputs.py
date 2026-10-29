# SPDX-License-Identifier: MIT
"""Experimento 01 · Nivel 1: clonar MT19937 con 624 salidas completas de 32 bits.

Para cada ensayo:

1. Se crea una víctima `random.Random(semilla)` de CPython con semilla aleatoria
   de 64 bits y se descarta un número aleatorio de salidas (0 a 2000), para que
   la observación empiece en cualquier punto respecto a los twists.
2. Se observan 624 salidas de `getrandbits(32)`.
3. Se mide el tiempo de `recover_state` (untemper de las 624 palabras).
4. Se predicen las 10 000 salidas siguientes y se mide la tasa de acierto.

Grupo de control: el mismo procedimiento sobre ChaCha20 y `os.urandom`.

Uso: uv run python experiments/e01_mt_full_outputs.py
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from functools import partial

import numpy as np

from prng_audit.core.attacks.mt19937_clone import (
    clone,
    prediction_accuracy,
    recover_state,
    temper_array,
    untemper,
    untemper_array,
)
from prng_audit.core.generators import ChaCha20Generator, OsUrandomGenerator
from prng_audit.core.generators.mt19937 import N

from _common import fmt_int, summarize, write_results

MASTER_SEED = 20261029
TRIALS = 100
CONTROL_TRIALS = 20
N_PREDICT = 10_000


def run_trial(next_u32: Callable[[], int], offset: int) -> dict[str, float]:
    for _ in range(offset):
        next_u32()
    observed = [next_u32() for _ in range(N)]
    t0 = time.perf_counter()
    recover_state(observed)
    t_recover = time.perf_counter() - t0
    cloned = clone(observed)
    predicted = [cloned.next_u32() for _ in range(N_PREDICT)]
    actual = [next_u32() for _ in range(N_PREDICT)]
    return {"t_recover_s": t_recover, "acierto": prediction_accuracy(predicted, actual)}


def untemper_throughput() -> dict[str, float]:
    rng = np.random.default_rng(MASTER_SEED)
    x = rng.integers(0, 2**32, size=1 << 22, dtype=np.uint32)
    t = temper_array(x)
    t0 = time.perf_counter()
    untemper_array(t)
    vec = len(x) / (time.perf_counter() - t0)
    sample = [int(v) for v in t[:100_000]]
    t0 = time.perf_counter()
    for v in sample:
        untemper(v)
    scalar = len(sample) / (time.perf_counter() - t0)
    return {"escalar_por_s": scalar, "numpy_por_s": vec}


def main() -> None:
    master = random.Random(MASTER_SEED)
    mt_trials = []
    for _ in range(TRIALS):
        seed = master.getrandbits(64)
        offset = master.randrange(0, 2001)
        victim = random.Random(seed)
        result = run_trial(partial(victim.getrandbits, 32), offset)
        mt_trials.append({"semilla": seed, "offset": offset, **result})

    controls: dict[str, list[dict[str, float]]] = {"chacha20": [], "os_urandom": []}
    for i in range(CONTROL_TRIALS):
        cha = ChaCha20Generator(master.getrandbits(64))
        controls["chacha20"].append(run_trial(cha.next_u32, i))
        osr = OsUrandomGenerator()
        controls["os_urandom"].append(run_trial(osr.next_u32, i))

    throughput = untemper_throughput()

    acc_mt = [t["acierto"] for t in mt_trials]
    time_mt = summarize([t["t_recover_s"] * 1000 for t in mt_trials])
    rows = [
        ("MT19937 (CPython)", TRIALS, N, min(acc_mt), sum(acc_mt) / TRIALS, time_mt["mediana"]),
    ]
    for name, trials in controls.items():
        acc = [t["acierto"] for t in trials]
        tm = summarize([t["t_recover_s"] * 1000 for t in trials])
        rows.append(
            (f"{name} (control)", CONTROL_TRIALS, N, min(acc), sum(acc) / len(acc), tm["mediana"])
        )

    table = [
        "# E01 · Clonado de MT19937 con salidas completas\n",
        f"Predicción de las {fmt_int(N_PREDICT)} salidas siguientes a la observación.\n",
        "| Generador | Ensayos | Salidas observadas | Acierto mínimo | Acierto medio "
        "| Tiempo de recuperación (mediana, ms) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, n, obs, amin, amean, tmed in rows:
        table.append(f"| {name} | {n} | {obs} | {amin:.2%} | {amean:.2%} | {tmed:.2f} |")
    table += [
        "",
        f"Tiempo de recuperación en MT19937: media {time_mt['media']:.2f} ms, "
        f"p95 {time_mt['p95']:.2f} ms, máximo {time_mt['max']:.2f} ms.",
        "",
        f"Rendimiento de `untemper`: {fmt_int(throughput['escalar_por_s'])} palabras/s en "
        f"Python puro, {fmt_int(throughput['numpy_por_s'])} palabras/s con NumPy.",
    ]
    write_results(
        "e01_mt_full_outputs",
        {
            "parametros": {
                "master_seed": MASTER_SEED,
                "ensayos": TRIALS,
                "ensayos_control": CONTROL_TRIALS,
                "predicciones": N_PREDICT,
            },
            "mt19937": mt_trials,
            "control": controls,
            "untemper_rendimiento": throughput,
        },
        "\n".join(table),
    )


if __name__ == "__main__":
    main()
