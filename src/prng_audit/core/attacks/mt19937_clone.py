# SPDX-License-Identifier: MIT
"""Ataque de nivel 1: clonar un MT19937 a partir de 624 salidas completas de 32 bits.

Idea en dos pasos:

1. **Invertir el tempering** (`untemper`). Cada salida es `temper(mt[i])` y el
   tempering es una biyección, así que de cada salida se recupera exactamente
   una palabra del estado.
2. **Reconstruir el estado.** 624 salidas consecutivas dan 624 palabras
   consecutivas de la secuencia interna x₀, x₁, x₂… del generador. La
   recurrencia de Matsumoto-Nishimura

       x[k+624] = x[k+397] ⊕ A·( (x[k] & 0x80000000) | (x[k+1] & 0x7FFFFFFF) )

   calcula cualquier palabra futura a partir de las 624 anteriores, así que
   esas 624 palabras son un estado completo.

No hace falta saber dónde empieza cada twist de la víctima: el twist "en el
sitio" del código de referencia aplicado a un vector con x[m], …, x[m+623]
produce x[m+624], …, x[m+1247] para cualquier m. Por eso el estado clonado es
siempre `MTState(palabras, pos=624)`, aunque la posición interna de la víctima
sea otra: la **secuencia de salidas** es la misma, que es lo que importa.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import numpy.typing as npt

from prng_audit.core.generators.base import MASK32
from prng_audit.core.generators.mt19937 import MT19937, TEMPERING_B, TEMPERING_C, MTState, N


def undo_xor_rshift(y: int, shift: int) -> int:
    """Invierte `y ^= y >> shift` sobre 32 bits.

    Los `shift` bits altos de la salida son los de la entrada (se hizo XOR con
    ceros). Con ellos se recuperan los `shift` bits siguientes, y así
    sucesivamente: cada vuelta del bucle fija `shift` bits más.
    """
    x = y
    for _ in range(32 // shift + 1):
        x = y ^ (x >> shift)
    return x & MASK32


def undo_xor_lshift_mask(y: int, shift: int, mask: int) -> int:
    """Invierte `y ^= (y << shift) & mask` sobre 32 bits.

    Simétrico al anterior, empezando por los `shift` bits bajos, que no cambian.
    """
    x = y
    for _ in range(32 // shift + 1):
        x = y ^ ((x << shift) & mask)
    return x & MASK32


def untemper(y: int) -> int:
    """Inversa exacta de `temper`: deshace los cuatro pasos en orden inverso."""
    y = undo_xor_rshift(y, 18)
    y = undo_xor_lshift_mask(y, 15, TEMPERING_C)
    y = undo_xor_lshift_mask(y, 7, TEMPERING_B)
    y = undo_xor_rshift(y, 11)
    return y


# --- Versiones vectorizadas (NumPy) -----------------------------------------
#
# Mismas operaciones sobre arrays de uint32. Sirven para comprobar
# `untemper(temper(x)) == x` para los 2³² valores posibles en segundos, y
# para atacar flujos largos en los experimentos.

U32Array = npt.NDArray[np.uint32]


def temper_array(y: U32Array) -> U32Array:
    y = y ^ (y >> np.uint32(11))
    y = y ^ ((y << np.uint32(7)) & np.uint32(TEMPERING_B))
    y = y ^ ((y << np.uint32(15)) & np.uint32(TEMPERING_C))
    y = y ^ (y >> np.uint32(18))
    return y


def _undo_rshift_array(y: U32Array, shift: int) -> U32Array:
    x = y.copy()
    for _ in range(32 // shift + 1):
        x = y ^ (x >> np.uint32(shift))
    return x


def _undo_lshift_mask_array(y: U32Array, shift: int, mask: int) -> U32Array:
    x = y.copy()
    for _ in range(32 // shift + 1):
        x = y ^ ((x << np.uint32(shift)) & np.uint32(mask))
    return x


def untemper_array(y: U32Array) -> U32Array:
    y = _undo_rshift_array(y, 18)
    y = _undo_lshift_mask_array(y, 15, TEMPERING_C)
    y = _undo_lshift_mask_array(y, 7, TEMPERING_B)
    y = _undo_rshift_array(y, 11)
    return y


# --- Reconstrucción del estado ----------------------------------------------


def recover_state(outputs: Sequence[int]) -> MTState:
    """Estado equivalente a partir de al menos 624 salidas consecutivas de `next_u32`.

    Se usan las 624 **últimas**, así que el clon continúa justo después de la
    última salida observada.
    """
    if len(outputs) < N:
        raise ValueError(f"hacen falta {N} salidas consecutivas, hay {len(outputs)}")
    window = outputs[-N:]
    if any(not 0 <= o <= MASK32 for o in window):
        raise ValueError("las salidas deben ser enteros de 32 bits sin signo")
    return MTState(words=tuple(untemper(o) for o in window), pos=N)


def clone(outputs: Sequence[int]) -> MT19937:
    """Un `MT19937` que produce las mismas salidas que la víctima a partir de ahora."""
    gen = MT19937(seed=0)
    gen.setstate(recover_state(outputs))
    return gen


def prediction_accuracy(predicted: Iterable[int], actual: Iterable[int]) -> float:
    """Fracción de aciertos posición a posición (las dos secuencias deben medir lo mismo)."""
    pairs = list(zip(predicted, actual, strict=True))
    if not pairs:
        raise ValueError("no hay nada que comparar")
    return sum(p == a for p, a in pairs) / len(pairs)
