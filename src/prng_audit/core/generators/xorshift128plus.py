# SPDX-License-Identifier: MIT
"""xorshift128+ (S. Vigna), con la variante que usa V8 para `Math.random()`.

Referencia del algoritmo: S. Vigna (2017), "Further scramblings of
Marsaglia's xorshift generators", Journal of Computational and Applied
Mathematics 315. Parámetros (a, b, c) = (23, 17, 26), los mismos que usa V8.

Referencia de V8 (consultada el 2026-10-29 en github.com/v8/v8, rama main):

- `src/base/utils/random-number-generator.h`: `XorShift128` y `MurmurHash3`.
- `src/numbers/math-random.cc` y `src/builtins/math.tq`: cómo `Math.random()`
  siembra el estado y convierte la salida a double.

Hay dos perfiles de `Math.random()`, porque V8 lo cambió:

- `"v8-cache"`: el de Node 22 (V8 12.4). Rellena una caché de 64 doubles de
  una vez, con `ToDouble(state0)` = 52 bits altos de `state0`, y los sirve del
  último al primero (LIFO). Validado contra `node --random-seed=N`.
- `"v8-direct"`: el de la rama main actual en 64 bits. Sin caché; cada
  llamada da un paso y devuelve `(s0 + s1) >> 11` dividido entre 2⁵³.
  Transcrito del código fuente; **no** validado contra un binario, porque en
  este entorno no hay un Node con ese V8. La versión exacta de V8 en que se
  introdujo el cambio está pendiente de verificar (TODO-VERIFICAR).
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from typing import Literal

from prng_audit.core.generators.base import MASK32, MASK64, PRNG

MathRandomProfile = Literal["v8-cache", "v8-direct"]

V8_CACHE_SIZE = 64


def murmurhash3_fmix64(h: int) -> int:
    """Mezclador final de 64 bits de MurmurHash3, tal como lo usa V8 para sembrar."""
    h &= MASK64
    h ^= h >> 33
    h = (h * 0xFF51AFD7ED558CCD) & MASK64
    h ^= h >> 33
    h = (h * 0xC4CEB9FE1A85EC53) & MASK64
    h ^= h >> 33
    return h


def xorshift128_step(s0: int, s1: int) -> tuple[int, int]:
    """Un paso de la transición de estado, igual que `XorShift128` de V8.

    Devuelve el nuevo par (state0, state1). La salida canónica de
    xorshift128+ es la suma de los dos, módulo 2⁶⁴.
    """
    x = s0
    y = s1
    x ^= (x << 23) & MASK64
    x ^= x >> 17
    x ^= y
    x ^= y >> 26
    return y, x


def v8_to_double(state0: int) -> float:
    """`ToDouble` de V8: 52 bits altos de state0 como mantisa de un double en [1, 2), menos 1."""
    bits = (state0 >> 12) | 0x3FF0000000000000
    value: float = struct.unpack("<d", struct.pack("<Q", bits))[0]
    return value - 1.0


@dataclass(frozen=True, slots=True)
class XorShiftState:
    """Estado de xorshift128+.

    `cache` y `cache_index` solo se usan en el perfil `"v8-cache"`: guardan la
    caché de doubles de `Math.random()` y cuántos quedan por servir.
    """

    s0: int
    s1: int
    cache: tuple[float, ...] = field(default=())
    cache_index: int = 0


class XorShift128Plus(PRNG[XorShiftState]):
    """xorshift128+ con salida canónica de 64 bits y `random()` como `Math.random()` de V8.

    - `next_u64()`: salida canónica (state0 + state1 tras el paso).
    - `next_u32()`: 32 bits altos de `next_u64()`. Los bits bajos de una suma
      son los de peor calidad, por eso se descartan.
    - `random()`: `Math.random()` según el perfil elegido.

    Las tres comparten el mismo estado, igual que en V8, pero en el perfil
    `"v8-cache"` `random()` consume pasos por bloques de 64.
    """

    name = "xorshift128plus"

    def __init__(self, seed: int | None = None, profile: MathRandomProfile = "v8-cache") -> None:
        if profile not in ("v8-cache", "v8-direct"):
            raise ValueError(f"perfil desconocido: {profile}")
        self.profile: MathRandomProfile = profile
        self._s0 = 0
        self._s1 = 0
        self._cache: list[float] = []
        self._cache_index = 0
        self.seed(seed)

    def seed(self, seed: int | None = None) -> None:
        """Siembra como `Math.random()` con `--random-seed`: dos MurmurHash3 de seed y ~seed."""
        if seed is None:
            seed = int.from_bytes(os.urandom(8), "little")
        seed &= MASK64
        self._s0 = murmurhash3_fmix64(seed)
        self._s1 = murmurhash3_fmix64(~seed & MASK64)
        if self._s0 == 0 and self._s1 == 0:
            raise ValueError("la semilla produce el estado prohibido (0, 0)")
        self._cache = []
        self._cache_index = 0

    def _step(self) -> None:
        self._s0, self._s1 = xorshift128_step(self._s0, self._s1)

    def next_u64(self) -> int:
        self._step()
        return (self._s0 + self._s1) & MASK64

    def next_u32(self) -> int:
        return (self.next_u64() >> 32) & MASK32

    def random(self) -> float:
        """Siguiente valor de `Math.random()` según el perfil."""
        if self.profile == "v8-direct":
            return (self.next_u64() >> 11) / 9007199254740992.0
        if self._cache_index == 0:
            cache = []
            for _ in range(V8_CACHE_SIZE):
                self._step()
                cache.append(v8_to_double(self._s0))
            self._cache = cache
            self._cache_index = V8_CACHE_SIZE
        self._cache_index -= 1
        return self._cache[self._cache_index]

    def getstate(self) -> XorShiftState:
        return XorShiftState(self._s0, self._s1, tuple(self._cache), self._cache_index)

    def setstate(self, state: XorShiftState) -> None:
        if not (0 <= state.s0 <= MASK64 and 0 <= state.s1 <= MASK64):
            raise ValueError("las dos palabras del estado son de 64 bits")
        if state.s0 == 0 and state.s1 == 0:
            raise ValueError("el estado (0, 0) está prohibido")
        if not 0 <= state.cache_index <= len(state.cache):
            raise ValueError("índice de caché fuera de rango")
        self._s0, self._s1 = state.s0, state.s1
        self._cache = list(state.cache)
        self._cache_index = state.cache_index
