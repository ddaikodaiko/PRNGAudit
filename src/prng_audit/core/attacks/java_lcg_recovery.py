# SPDX-License-Identifier: MIT
"""Ataque de nivel 5: recuperar el estado de `java.util.Random` a partir de dos `nextInt()`.

Cada `nextInt()` devuelve los 32 bits altos del estado de 48 bits recién
calculado. Tras la primera salida o₁, el estado es

    s₁ = o₁ · 2¹⁶ + b,   con b ∈ [0, 2¹⁶) desconocido.

Se prueban los 65 536 valores de b: para cada uno se calcula el siguiente
estado s₂ = (s₁·M + A) mod 2⁴⁸ y se comprueba si sus 32 bits altos coinciden
con la segunda salida o₂. Con el estado s₂ ya se pueden predecir todas las
salidas siguientes.

Un candidato falso (que coincida con o₂ por casualidad) tiene probabilidad de
aproximadamente 2¹⁶/2³² = 2⁻¹⁶. Por eso la función devuelve una lista y, si
hay una tercera salida, se usa para descartar los falsos.

Como M es impar, tiene inverso módulo 2⁴⁸ y el LCG se puede ejecutar hacia
atrás: así se recupera también el estado inicial y, deshaciendo la mezcla
`semilla ⊕ M`, los 48 bits bajos de la semilla original.
"""

from __future__ import annotations

from collections.abc import Sequence

from prng_audit.core.generators.base import MASK32
from prng_audit.core.generators.java_lcg import ADDEND, MASK48, MULTIPLIER, JavaRandom

#: Inverso multiplicativo de M módulo 2⁴⁸: M · M⁻¹ ≡ 1 (mod 2⁴⁸).
MULTIPLIER_INV = pow(MULTIPLIER, -1, 1 << 48)


def next_state(s: int) -> int:
    return (s * MULTIPLIER + ADDEND) & MASK48


def previous_state(s: int) -> int:
    """Deshace un paso: s_prev = (s − A) · M⁻¹ mod 2⁴⁸."""
    return ((s - ADDEND) * MULTIPLIER_INV) & MASK48


def recover_states_from_ints(outputs: Sequence[int]) -> list[int]:
    """Estados posibles **después** de la última salida observada.

    `outputs` son salidas consecutivas de `nextInt()` (con signo, como en Java,
    o sin signo: solo se usan sus 32 bits bajos). Hacen falta al menos dos; las
    que sobren se usan para descartar candidatos falsos.
    """
    if len(outputs) < 2:
        raise ValueError("hacen falta al menos dos salidas consecutivas de nextInt()")
    obs = [o & MASK32 for o in outputs]
    high = obs[0] << 16
    survivors = []
    for low in range(1 << 16):
        s = high | low
        for o in obs[1:]:
            s = next_state(s)
            if s >> 16 != o:
                break
        else:
            survivors.append(s)
    return survivors


def recover_state_from_long(value: int) -> int:
    """Estado después de un `nextLong()`, que son dos `next(32)` seguidos.

    `nextLong() = (next(32) << 32) + next(32)` con signo, así que la mitad alta
    lleva el posible acarreo de la mitad baja si esta es negativa. Se deshace
    y se reduce al caso de dos `nextInt()`. Si queda más de un candidato (un
    falso positivo, probabilidad ≈ 2⁻¹⁶), se pide otra salida.
    """
    v = value & ((1 << 64) - 1)
    lo = v & MASK32
    hi = (v >> 32) & MASK32
    if lo & 0x80000000:
        # La mitad baja era negativa: al sumarla se restó 1 a la mitad alta.
        hi = (hi + 1) & MASK32
    candidates = recover_states_from_ints([hi, lo])
    if len(candidates) != 1:
        raise ValueError(f"{len(candidates)} estados compatibles; hace falta otra salida")
    return candidates[0]


def clone(state: int) -> JavaRandom:
    """`JavaRandom` situado en el estado recuperado."""
    gen = JavaRandom(0)
    gen.setstate(state)
    return gen


def recover_seed(state: int, steps_back: int) -> int:
    """Los 48 bits bajos de la semilla original, retrocediendo `steps_back` pasos.

    `steps_back` es cuántas llamadas a `next()` hubo desde `new Random(seed)`
    hasta el estado dado (por ejemplo, 2 si se observaron las dos primeras
    salidas). Los 16 bits altos de una semilla de 64 bits se pierden en la
    mezcla inicial y no se pueden recuperar.
    """
    if steps_back < 0:
        raise ValueError("steps_back no puede ser negativo")
    s = state
    for _ in range(steps_back):
        s = previous_state(s)
    return s ^ MULTIPLIER
