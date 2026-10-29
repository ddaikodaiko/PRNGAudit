# SPDX-License-Identifier: MIT
"""Generadores criptográficamente seguros (grupo de control).

- `OsUrandomGenerator`: lee del generador del sistema operativo
  (`os.urandom`, que es lo mismo que usan `secrets` y `random.SystemRandom`).
  No tiene semilla ni estado observable: es lo que debería usar un casino.
- `ChaCha20Generator`: flujo de clave de ChaCha20 (RFC 8439) a través de la
  librería `cryptography`. Es determinista a partir de una clave, lo que
  permite repetir experimentos, pero sin conocer la clave sus salidas no
  permiten reconstruir el estado: eso es lo que significa "criptográficamente
  seguro" y lo que los ataques del proyecto deben confirmar al fallar.

Ninguno de los dos es "más aleatorio" estadísticamente que el MT: la
diferencia está en la predictibilidad, que es la tesis del proyecto.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from prng_audit.core.generators.base import PRNG, NotSupportedError

CHACHA_BLOCK = 64
#: Bloques de ChaCha20 que se calculan de una vez (4 KiB de flujo).
CHACHA_BUFFER_BLOCKS = 64
CHACHA_MAX_BLOCKS = 1 << 32


class OsUrandomGenerator(PRNG[None]):
    """Palabras de 32 bits leídas de `os.urandom`."""

    name = "os_urandom"

    def __init__(self, buffer_size: int = 4096) -> None:
        if buffer_size < 4 or buffer_size % 4:
            raise ValueError("el tamaño del búfer debe ser un múltiplo positivo de 4")
        self._buffer_size = buffer_size
        self._buffer = b""
        self._offset = 0

    def next_u32(self) -> int:
        if self._offset >= len(self._buffer):
            self._buffer = os.urandom(self._buffer_size)
            self._offset = 0
        word = int.from_bytes(self._buffer[self._offset : self._offset + 4], "little")
        self._offset += 4
        return word

    def seed(self, seed: int | None = None) -> None:
        """Solo admite `None` (no hace nada): el sistema operativo gestiona su propia semilla."""
        if seed is not None:
            raise NotSupportedError("os.urandom no admite semilla")

    def getstate(self) -> None:
        raise NotSupportedError("el estado de os.urandom no es accesible")

    def setstate(self, state: None) -> None:
        raise NotSupportedError("el estado de os.urandom no es accesible")


@dataclass(frozen=True, slots=True)
class ChaChaState:
    """Clave de 32 bytes, nonce de 12 bytes y posición en bytes dentro del flujo."""

    key: bytes
    nonce: bytes
    position: int

    def __post_init__(self) -> None:
        if len(self.key) != 32:
            raise ValueError("la clave de ChaCha20 es de 32 bytes")
        if len(self.nonce) != 12:
            raise ValueError("el nonce de ChaCha20 (RFC 8439) es de 12 bytes")
        if self.position < 0 or self.position % 4:
            raise ValueError("la posición debe ser un múltiplo no negativo de 4")


def derive_key(seed: int) -> bytes:
    """Clave de 32 bytes a partir de una semilla entera (SHA-256 de su codificación).

    Ojo: esto no añade entropía. Si la semilla es de 32 bits, la clave también
    tiene solo 2³² posibilidades y se puede buscar por fuerza bruta. Esa es la
    clase de fallo de implementación que modela el casino simulado.
    """
    n = abs(seed)
    raw = n.to_bytes(max(1, (n.bit_length() + 7) // 8), "little")
    sign = b"-" if seed < 0 else b"+"
    return hashlib.sha256(b"prng-audit/chacha20/" + sign + raw).digest()


class ChaCha20Generator(PRNG[ChaChaState]):
    """Flujo de ChaCha20 cortado en palabras de 32 bits little-endian.

    El contador de bloque de 32 bits empieza en 0, así que una clave y un nonce
    dan como máximo 2³² bloques (256 GiB) antes de tener que cambiar de nonce.
    """

    name = "chacha20"

    def __init__(self, seed: int | None = None) -> None:
        self._key = b"\x00" * 32
        self._nonce = b"\x00" * 12
        self._position = 0
        self._buffer = b""
        self._buffer_start = 0
        self.seed(seed)

    @classmethod
    def from_key(cls, key: bytes, nonce: bytes = b"\x00" * 12) -> ChaCha20Generator:
        gen = cls(seed=0)
        gen.setstate(ChaChaState(key=key, nonce=nonce, position=0))
        return gen

    def seed(self, seed: int | None = None) -> None:
        """Con entero: clave de `derive_key` y nonce cero. Con `None`: clave y nonce aleatorios."""
        if seed is None:
            key, nonce = os.urandom(32), os.urandom(12)
        else:
            key, nonce = derive_key(seed), b"\x00" * 12
        self.setstate(ChaChaState(key=key, nonce=nonce, position=0))

    def _keystream(self, first_block: int, n_blocks: int) -> bytes:
        if first_block + n_blocks > CHACHA_MAX_BLOCKS:
            n_blocks = CHACHA_MAX_BLOCKS - first_block
            if n_blocks <= 0:
                raise OverflowError("flujo de ChaCha20 agotado para esta clave y nonce")
        # `cryptography` usa un nonce de 16 bytes: contador de 32 bits
        # little-endian seguido del nonce de 96 bits del RFC 8439.
        full_nonce = first_block.to_bytes(4, "little") + self._nonce
        encryptor = Cipher(algorithms.ChaCha20(self._key, full_nonce), mode=None).encryptor()
        return encryptor.update(b"\x00" * (CHACHA_BLOCK * n_blocks))

    def next_bytes(self, n: int) -> bytes:
        """Siguientes n bytes del flujo de clave (n múltiplo de 4)."""
        if n < 0 or n % 4:
            raise ValueError("n debe ser un múltiplo no negativo de 4")
        out = bytearray()
        while len(out) < n:
            offset = self._position - self._buffer_start
            if not 0 <= offset < len(self._buffer):
                block = self._position // CHACHA_BLOCK
                self._buffer = self._keystream(block, CHACHA_BUFFER_BLOCKS)
                self._buffer_start = block * CHACHA_BLOCK
                offset = self._position - self._buffer_start
            take = min(n - len(out), len(self._buffer) - offset)
            out += self._buffer[offset : offset + take]
            self._position += take
        return bytes(out)

    def next_u32(self) -> int:
        return int.from_bytes(self.next_bytes(4), "little")

    def getstate(self) -> ChaChaState:
        return ChaChaState(key=self._key, nonce=self._nonce, position=self._position)

    def setstate(self, state: ChaChaState) -> None:
        self._key = state.key
        self._nonce = state.nonce
        self._position = state.position
        self._buffer = b""
        self._buffer_start = 0
