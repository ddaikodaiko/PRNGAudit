# SPDX-License-Identifier: MIT
"""Mersenne Twister MT19937, implementado desde cero.

Referencia: M. Matsumoto y T. Nishimura (1998), "Mersenne Twister: a
623-dimensionally equidistributed uniform pseudo-random number generator",
ACM TOMACS 8(1). Las rutinas de siembra `init_genrand` e `init_by_array`
siguen el código de referencia de los autores (versión de 2002, `mt19937ar.c`).

El estado son 624 palabras de 32 bits más una posición. Cada salida es una
palabra del estado pasada por la función de *tempering*, que es invertible.
Cuando se gastan las 624 palabras, se regeneran todas a la vez con el
*twist*. Ambas operaciones son lineales sobre GF(2): esa es la raíz de todos
los ataques del módulo `attacks`.

Hay dos formas de sembrar y conviene no confundirlas:

- `init_genrand(s)`: semilla de 32 bits. Es la que usa
  `numpy.random.RandomState(int)`.
- `init_by_array(key)`: semilla como lista de palabras de 32 bits. Es la que
  usa CPython: `random.seed(n)` trocea |n| en palabras de 32 bits, empezando
  por la menos significativa.

`MT19937.seed(n)` sigue a CPython, porque el casino simulado está escrito en
Python. Para reproducir NumPy se usa `init_genrand`.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from prng_audit.core.generators.base import MASK32, PRNG

N = 624
M = 397
MATRIX_A = 0x9908B0DF
UPPER_MASK = 0x80000000
LOWER_MASK = 0x7FFFFFFF

TEMPERING_B = 0x9D2C5680
TEMPERING_C = 0xEFC60000


def temper(y: int) -> int:
    """Función de tempering de MT19937 sobre una palabra de 32 bits."""
    y ^= y >> 11
    y ^= (y << 7) & TEMPERING_B
    y ^= (y << 15) & TEMPERING_C
    y ^= y >> 18
    return y & MASK32


@dataclass(frozen=True, slots=True)
class MTState:
    """Estado completo de MT19937.

    `pos` es el índice de la próxima palabra que se va a templar; si vale 624,
    la siguiente llamada hace primero el twist. CPython (`index`) y NumPy
    (`pos`) usan la misma convención, así que el estado es intercambiable.
    """

    words: tuple[int, ...]
    pos: int

    def __post_init__(self) -> None:
        if len(self.words) != N:
            raise ValueError(f"el estado de MT19937 tiene {N} palabras, no {len(self.words)}")
        if not 0 <= self.pos <= N:
            raise ValueError(f"posición fuera de rango: {self.pos}")
        if any(not 0 <= w <= MASK32 for w in self.words):
            raise ValueError("todas las palabras deben ser de 32 bits sin signo")


class MT19937(PRNG[MTState]):
    """Mersenne Twister de 32 bits, compatible bit a bit con CPython y NumPy."""

    name = "mt19937"

    def __init__(self, seed: int | None = None) -> None:
        self._mt: list[int] = [0] * N
        self._pos: int = N
        self.seed(seed)

    # --- Siembra --------------------------------------------------------

    def init_genrand(self, s: int) -> None:
        """Siembra con una sola palabra de 32 bits (código de referencia)."""
        mt = self._mt
        mt[0] = s & MASK32
        for i in range(1, N):
            mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & MASK32
        self._pos = N

    def init_by_array(self, key: Sequence[int]) -> None:
        """Siembra con una lista de palabras de 32 bits (código de referencia)."""
        if len(key) == 0:
            raise ValueError("la clave de siembra no puede estar vacía")
        self.init_genrand(19650218)
        mt = self._mt
        i, j = 1, 0
        for _ in range(max(N, len(key))):
            mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525)) + key[j] + j) & MASK32
            i += 1
            j += 1
            if i >= N:
                mt[0] = mt[N - 1]
                i = 1
            if j >= len(key):
                j = 0
        for _ in range(N - 1):
            mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941)) - i) & MASK32
            i += 1
            if i >= N:
                mt[0] = mt[N - 1]
                i = 1
        # Garantiza que el estado no es todo ceros (el único estado prohibido).
        mt[0] = 0x80000000
        self._pos = N

    def seed(self, seed: int | None = None) -> None:
        """Siembra igual que `random.seed(n)` de CPython para enteros.

        Con `None`, CPython lee 624 palabras de `os.urandom` y las usa como
        clave de `init_by_array`; aquí se hace lo mismo.
        """
        if seed is None:
            raw = os.urandom(4 * N)
            key = [int.from_bytes(raw[4 * i : 4 * i + 4], "little") for i in range(N)]
            self.init_by_array(key)
            return
        n = abs(seed)
        key = []
        while n:
            key.append(n & MASK32)
            n >>= 32
        self.init_by_array(key or [0])

    # --- Generación -----------------------------------------------------

    def twist(self) -> None:
        """Regenera las 624 palabras del estado (recurrencia de Matsumoto-Nishimura).

        Cada palabra nueva combina el bit alto de mt[i], los 31 bits bajos de
        mt[i+1] y la palabra mt[i+397]. Como se actualiza en el sitio, a partir
        de i = 227 el término mt[i+397] ya es una palabra nueva: así lo hace el
        código de referencia y así hay que hacerlo para obtener la misma
        secuencia.
        """
        mt = self._mt
        for i in range(N):
            y = (mt[i] & UPPER_MASK) | (mt[(i + 1) % N] & LOWER_MASK)
            mt[i] = mt[(i + M) % N] ^ (y >> 1) ^ (MATRIX_A if y & 1 else 0)
        self._pos = 0

    def next_u32(self) -> int:
        if self._pos >= N:
            self.twist()
        y = self._mt[self._pos]
        self._pos += 1
        return temper(y)

    # --- Estado ---------------------------------------------------------

    def getstate(self) -> MTState:
        return MTState(words=tuple(self._mt), pos=self._pos)

    def setstate(self, state: MTState) -> None:
        self._mt = list(state.words)
        self._pos = state.pos


# --- Conversión de estados con CPython y NumPy ------------------------------
#
# Permiten comprobar que nuestra implementación y las de referencia están en
# el mismo punto exacto de la secuencia, y más adelante inyectar en ellas un
# estado reconstruido por un ataque.


def from_cpython_state(state: tuple[Any, ...]) -> MTState:
    """Convierte el resultado de `random.getstate()` (versión 3) a `MTState`."""
    version, internal, _gauss_next = state
    if version != 3:
        raise ValueError(f"versión de estado de CPython no soportada: {version}")
    *words, pos = internal
    return MTState(words=tuple(int(w) for w in words), pos=int(pos))


def to_cpython_state(state: MTState) -> tuple[Any, ...]:
    """Convierte un `MTState` al formato de `random.setstate()`."""
    return (3, (*state.words, state.pos), None)


def from_numpy_state(state: tuple[Any, ...]) -> MTState:
    """Convierte `numpy.random.RandomState.get_state()` a `MTState`."""
    kind, keys, pos = state[0], state[1], state[2]
    if kind != "MT19937":
        raise ValueError(f"el estado de NumPy no es de MT19937: {kind}")
    return MTState(words=tuple(int(w) for w in keys), pos=int(pos))


def to_numpy_state(state: MTState) -> tuple[Any, ...]:
    """Convierte un `MTState` al formato de `RandomState.set_state()`.

    Se importa NumPy aquí dentro para que el núcleo no dependa de él solo
    por esta conversión.
    """
    import numpy as np

    return ("MT19937", np.array(state.words, dtype=np.uint32), state.pos, 0, 0.0)
