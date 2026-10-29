# SPDX-License-Identifier: MIT
"""Experimento 05 · Nivel 5: recuperar `java.util.Random` a partir de `nextInt()`.

Para cada ensayo:

1. Víctima `JavaRandom(semilla)` con semilla aleatoria de 64 bits (la réplica
   validada bit a bit contra el JDK en tests/generators/test_java_lcg.py), y un
   número aleatorio de salidas descartadas (0 a 2000).
2. Se observan 2 salidas de `nextInt()` y se cuentan los estados candidatos.
   Con 3 salidas se mide si el candidato queda único.
3. Se mide el tiempo de la búsqueda de los 2¹⁶ candidatos.
4. Con el estado se predicen las 10 000 salidas siguientes, y además 1 000
   tiradas de `nextInt(37)` (una ruleta europea).

Grupo de control: salidas de ChaCha20 tratadas como si fueran de Java.

Uso: uv run python experiments/e05_java_lcg.py
"""

from __future__ import annotations

import random
import time
from typing import Any

from prng_audit.core.attacks.java_lcg_recovery import clone, recover_states_from_ints
from prng_audit.core.attacks.mt19937_clone import prediction_accuracy
from prng_audit.core.generators import ChaCha20Generator, JavaRandom

from _common import fmt_int, summarize, write_results

MASTER_SEED = 20261029
TRIALS = 100
CONTROL_TRIALS = 1000
N_PREDICT = 10_000


def main() -> None:
    master = random.Random(MASTER_SEED)
    trials: list[dict[str, Any]] = []
    for _ in range(TRIALS):
        seed = master.getrandbits(64) - 2**63
        offset = master.randrange(0, 2001)
        victim = JavaRandom(seed)
        for _ in range(offset):
            victim.next_int()
        observed = [victim.next_int() for _ in range(3)]

        t0 = time.perf_counter()
        cands2 = recover_states_from_ints(observed[:2])
        t2 = time.perf_counter() - t0
        cands3 = recover_states_from_ints(observed)

        # Se ataca con 3 salidas para que el estado sea único.
        state = cands3[0]
        gen = clone(state)
        pred = [gen.next_int() for _ in range(N_PREDICT)]
        actual = [victim.next_int() for _ in range(N_PREDICT)]
        roulette_pred = [gen.next_int(37) for _ in range(1000)]
        roulette_act = [victim.next_int(37) for _ in range(1000)]
        trials.append(
            {
                "semilla": seed,
                "offset": offset,
                "candidatos_2_salidas": len(cands2),
                "candidatos_3_salidas": len(cands3),
                "t_busqueda_s": t2,
                "acierto_nextInt": prediction_accuracy(pred, actual),
                "acierto_ruleta": prediction_accuracy(roulette_pred, roulette_act),
            }
        )

    control_cands2 = []
    control_cands3 = []
    cha = ChaCha20Generator(master.getrandbits(64))
    for _ in range(CONTROL_TRIALS):
        outs = [cha.next_u32() for _ in range(3)]
        control_cands2.append(len(recover_states_from_ints(outs[:2])))
        control_cands3.append(len(recover_states_from_ints(outs)))

    t_ms = summarize([t["t_busqueda_s"] * 1000 for t in trials])
    acc = [t["acierto_nextInt"] for t in trials]
    acc_r = [t["acierto_ruleta"] for t in trials]
    unique2 = sum(t["candidatos_2_salidas"] == 1 for t in trials)
    unique3 = sum(t["candidatos_3_salidas"] == 1 for t in trials)

    table = "\n".join(
        [
            "# E05 · Recuperación del LCG de java.util.Random\n",
            "| Métrica | Valor |",
            "|---|---:|",
            f"| Ensayos | {TRIALS} |",
            "| Salidas `nextInt()` observadas | 2 (3 para garantizar unicidad) |",
            f"| Ensayos con candidato único usando 2 salidas | {unique2}/{TRIALS} |",
            f"| Ensayos con candidato único usando 3 salidas | {unique3}/{TRIALS} |",
            f"| Tiempo de búsqueda de 2¹⁶ candidatos (mediana) | {t_ms['mediana']:.1f} ms |",
            f"| Tiempo de búsqueda (p95 / máximo) | {t_ms['p95']:.1f} / {t_ms['max']:.1f} ms |",
            f"| Acierto en las {fmt_int(N_PREDICT)} `nextInt()` siguientes (mínimo) "
            f"| {min(acc):.2%} |",
            f"| Acierto en 1000 tiradas de ruleta `nextInt(37)` (mínimo) | {min(acc_r):.2%} |",
            "",
            "## Control: ChaCha20 tratado como si fuera Java\n",
            "| Métrica | Valor |",
            "|---|---:|",
            f"| Ensayos | {CONTROL_TRIALS} |",
            f"| Estados compatibles con 2 salidas (total) | {sum(control_cands2)} |",
            f"| Estados compatibles con 3 salidas (total) | {sum(control_cands3)} |",
            f"| Esperado por azar con 2 salidas (total) | ≈ {CONTROL_TRIALS * 2**16 / 2**32:.3f} |",
        ]
    )
    write_results(
        "e05_java_lcg",
        {
            "parametros": {
                "master_seed": MASTER_SEED,
                "ensayos": TRIALS,
                "ensayos_control": CONTROL_TRIALS,
                "predicciones": N_PREDICT,
            },
            "ensayos": trials,
            "control": {"candidatos_2": control_cands2, "candidatos_3": control_cands3},
        },
        table,
    )


if __name__ == "__main__":
    main()
