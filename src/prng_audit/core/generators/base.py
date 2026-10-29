# SPDX-License-Identifier: MIT
"""Interfaz común de todos los generadores del proyecto.

Cada generador concreto solo tiene que saber producir palabras de 32 bits
(`next_u32`) y gestionar su semilla y su estado. Las conversiones a otros
formatos (`getrandbits`, `random`) se implementan aquí una sola vez, copiando
la semántica exacta de CPython (`Modules/_randommodule.c`). Así, cuando un
juego del casino simulado pide `getrandbits(5)`, sabemos exactamente qué bits
del generador se filtran, que es justo lo que necesitan los ataques.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

MASK32 = 0xFFFFFFFF
MASK64 = 0xFFFFFFFFFFFFFFFF


class NotSupportedError(RuntimeError):
    """La operación no tiene sentido para este generador.

    Por ejemplo, `os.urandom` no tiene semilla ni un estado que se pueda
    leer: pedirle `getstate()` es un error de diseño, no un fallo puntual.
    """


class PRNG[StateT](ABC):
    """Generador de números pseudoaleatorios con salida básica de 32 bits.

    `StateT` es el tipo del estado interno que devuelven `getstate()` y
    `setstate()`. Cada generador define el suyo: para el MT, 624 palabras y
    una posición; para el LCG de Java, un entero de 48 bits.
    """

    #: Nombre corto y estable, usado en informes y en la API.
    name: str = "prng"

    @abstractmethod
    def next_u32(self) -> int:
        """Devuelve la siguiente palabra de 32 bits sin signo."""

    @abstractmethod
    def seed(self, seed: int | None = None) -> None:
        """Reinicia el generador a partir de una semilla entera.

        `None` significa "semilla tomada de la entropía del sistema".
        """

    @abstractmethod
    def getstate(self) -> StateT:
        """Devuelve una copia inmutable del estado interno completo."""

    @abstractmethod
    def setstate(self, state: StateT) -> None:
        """Restaura un estado obtenido con `getstate()`."""

    def getrandbits(self, k: int) -> int:
        """Entero de k bits con la semántica exacta de `random.getrandbits`.

        - k ≤ 32: una sola palabra, de la que se toman los k bits **altos**.
        - k > 32: se encadenan palabras empezando por la menos significativa
          (little-endian); de la última solo se toman sus bits altos.

        Que se tomen los bits altos y no los bajos es importante para el
        ataque con salidas truncadas (nivel 3).
        """
        if k < 0:
            raise ValueError("el número de bits no puede ser negativo")
        if k == 0:
            return 0
        if k <= 32:
            return self.next_u32() >> (32 - k)
        result = 0
        shift = 0
        remaining = k
        while remaining > 0:
            word = self.next_u32()
            if remaining < 32:
                word >>= 32 - remaining
            result |= word << shift
            shift += 32
            remaining -= 32
        return result

    def random(self) -> float:
        """Float en [0, 1) con 53 bits, como `random.random()` de CPython.

        Consume dos palabras: de la primera se quedan los 27 bits altos (a) y
        de la segunda los 26 bits altos (b). El resultado es
        (a·2²⁶ + b) / 2⁵³.

        Los generadores que imitan a otra plataforma (Java, V8) sobrescriben
        este método con la conversión nativa de esa plataforma.
        """
        a = self.next_u32() >> 5
        b = self.next_u32() >> 6
        return (a * 67108864.0 + b) * (1.0 / 9007199254740992.0)
