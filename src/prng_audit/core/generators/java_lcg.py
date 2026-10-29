# SPDX-License-Identifier: MIT
"""Generador congruencial lineal de `java.util.Random`.

Especificación: documentación de la clase `java.util.Random` del JDK, que fija
el algoritmo para que todas las JVM den la misma secuencia con la misma
semilla (D. Knuth, TAOCP vol. 2, §3.2.1).

Estado: un entero de 48 bits. Cada paso hace

    seed ← (seed · 0x5DEECE66D + 0xB) mod 2⁴⁸

y devuelve los `bits` bits **altos** del nuevo estado. Como `nextInt()`
devuelve 32 de esos 48 bits, a un atacante solo le faltan 16 bits por
adivinar: con dos salidas consecutivas basta para recuperar el estado entero
(ataque de nivel 5).
"""

from __future__ import annotations

import os

from prng_audit.core.generators.base import MASK32, MASK64, PRNG

MULTIPLIER = 0x5DEECE66D
ADDEND = 0xB
MASK48 = (1 << 48) - 1
DOUBLE_UNIT = 1.0 / (1 << 53)


def to_int32(x: int) -> int:
    """Interpreta los 32 bits bajos de x como un `int` de Java (con signo)."""
    x &= MASK32
    return x - (1 << 32) if x & 0x80000000 else x


def to_int64(x: int) -> int:
    """Interpreta los 64 bits bajos de x como un `long` de Java (con signo)."""
    x &= MASK64
    return x - (1 << 64) if x & (1 << 63) else x


def scramble(seed: int) -> int:
    """Transformación que aplica `new Random(seed)` / `setSeed(seed)`."""
    return (seed ^ MULTIPLIER) & MASK48


class JavaRandom(PRNG[int]):
    """Réplica exacta de `java.util.Random`.

    Los métodos con nombre Java (`next_int`, `next_long`, `next_double`...)
    devuelven los mismos valores, con signo incluido, que la JVM. `next_u32`
    es `next(32)` visto sin signo, para encajar en la interfaz común.

    El estado (`getstate`) es el valor interno de 48 bits *ya mezclado*, no la
    semilla que se pasó al constructor.
    """

    name = "java_lcg"

    def __init__(self, seed: int | None = None) -> None:
        self._state = 0
        self.seed(seed)

    def seed(self, seed: int | None = None) -> None:
        """Igual que `setSeed(long)`. Con `None`, semilla de 64 bits del sistema.

        (La JVM sin semilla usa `seedUniquifier() ^ System.nanoTime()`; aquí
        no se imita porque no aporta nada al estudio: el ataque de semilla por
        tiempo se modela en el casino, no en el generador.)
        """
        if seed is None:
            seed = int.from_bytes(os.urandom(8), "little")
        self._state = scramble(seed)

    def next_bits(self, bits: int) -> int:
        """`protected int next(int bits)`, devuelto sin signo."""
        if not 1 <= bits <= 32:
            raise ValueError("bits debe estar entre 1 y 32")
        self._state = (self._state * MULTIPLIER + ADDEND) & MASK48
        return self._state >> (48 - bits)

    def next_u32(self) -> int:
        return self.next_bits(32)

    def next_int(self, bound: int | None = None) -> int:
        """`nextInt()` o `nextInt(bound)`.

        Con cota, Java usa muestreo con rechazo para evitar sesgo: descarta
        valores de `next(31)` que caen en el último trozo incompleto. Si la cota
        es potencia de dos, toma directamente los bits altos.
        """
        if bound is None:
            return to_int32(self.next_bits(32))
        if bound <= 0:
            raise ValueError("bound debe ser positivo")
        r = self.next_bits(31)
        m = bound - 1
        if bound & m == 0:
            return (bound * r) >> 31
        u = r
        # En Java la condición es `u - (r = u % bound) + m < 0`, que detecta el
        # desbordamiento de un int de 32 bits; aquí, sin desbordamiento, es ≥ 2³¹.
        while True:
            r = u % bound
            if u - r + m < (1 << 31):
                return r
            u = self.next_bits(31)

    def next_long(self) -> int:
        """`nextLong()`: `((long) next(32) << 32) + next(32)`, con signo."""
        hi = to_int32(self.next_bits(32))
        lo = to_int32(self.next_bits(32))
        return to_int64((hi << 32) + lo)

    def next_boolean(self) -> bool:
        return self.next_bits(1) != 0

    def next_float(self) -> float:
        return self.next_bits(24) / float(1 << 24)

    def next_double(self) -> float:
        """`nextDouble()`: 26 + 27 bits altos de dos pasos, entre 2⁵³."""
        return ((self.next_bits(26) << 27) + self.next_bits(27)) * DOUBLE_UNIT

    def random(self) -> float:
        """La conversión a float nativa de Java es `nextDouble()`."""
        return self.next_double()

    def getstate(self) -> int:
        return self._state

    def setstate(self, state: int) -> None:
        if not 0 <= state <= MASK48:
            raise ValueError("el estado de java.util.Random es de 48 bits")
        self._state = state
