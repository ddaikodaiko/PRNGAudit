# SPDX-License-Identifier: MIT
"""Grupo de control: ChaCha20 contra los vectores del RFC 8439 y os.urandom."""

from __future__ import annotations

import pytest

from prng_audit.core.generators.base import NotSupportedError
from prng_audit.core.generators.csprng import (
    ChaCha20Generator,
    ChaChaState,
    OsUrandomGenerator,
    derive_key,
)

# RFC 8439, §2.3.2: clave 00..1f, nonce 000000090000004a00000000, contador 1.
RFC8439_2_3_2_KEY = bytes(range(32))
RFC8439_2_3_2_NONCE = bytes.fromhex("000000090000004a00000000")
RFC8439_2_3_2_BLOCK = bytes.fromhex(
    "10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e"
    "d2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e"
)

# RFC 8439, apéndice A.1, vector 1: clave y nonce a cero, contador 0.
RFC8439_A1_1_BLOCK = bytes.fromhex(
    "76b8e0ada0f13d90405d6ae55386bd28bdd219b8a08ded1aa836efcc8b770dc7"
    "da41597c5157488d7724e03fb8d84a376a43b8f41518a11cc387b669b2ee6586"
)


def test_rfc8439_block_function_vector() -> None:
    gen = ChaCha20Generator.from_key(RFC8439_2_3_2_KEY, RFC8439_2_3_2_NONCE)
    gen.setstate(ChaChaState(RFC8439_2_3_2_KEY, RFC8439_2_3_2_NONCE, position=64))
    assert gen.next_bytes(64) == RFC8439_2_3_2_BLOCK


def test_rfc8439_appendix_a1_vector_and_word_order() -> None:
    gen = ChaCha20Generator.from_key(b"\x00" * 32)
    assert gen.next_bytes(64) == RFC8439_A1_1_BLOCK
    gen = ChaCha20Generator.from_key(b"\x00" * 32)
    words = [gen.next_u32() for _ in range(16)]
    expected = [int.from_bytes(RFC8439_A1_1_BLOCK[i : i + 4], "little") for i in range(0, 64, 4)]
    assert words == expected


def test_seeded_chacha_is_reproducible_and_restorable() -> None:
    a = ChaCha20Generator(123)
    b = ChaCha20Generator(123)
    assert [a.next_u32() for _ in range(5000)] == [b.next_u32() for _ in range(5000)]
    state = a.getstate()
    ahead = [a.next_u32() for _ in range(3000)]
    c = ChaCha20Generator(0)
    c.setstate(state)
    assert [c.next_u32() for _ in range(3000)] == ahead


def test_seek_across_buffer_boundaries() -> None:
    """Saltar a cualquier posición da lo mismo que avanzar palabra a palabra."""
    seq = ChaCha20Generator(9)
    stream = [seq.next_u32() for _ in range(3000)]
    for pos in (0, 4, 60, 64, 4092, 4096, 4100, 8000):
        gen = ChaCha20Generator(9)
        gen.setstate(ChaChaState(gen.getstate().key, gen.getstate().nonce, pos))
        assert gen.next_u32() == stream[pos // 4]


def test_derive_key_distinguishes_sign_and_value() -> None:
    keys = {derive_key(s) for s in (0, 1, -1, 2**64, 255, 256)}
    assert len(keys) == 6


def test_os_urandom_has_no_seed_or_state() -> None:
    gen = OsUrandomGenerator()
    gen.seed(None)
    with pytest.raises(NotSupportedError):
        gen.seed(1)
    with pytest.raises(NotSupportedError):
        gen.getstate()
    with pytest.raises(NotSupportedError):
        gen.setstate(None)
    values = [gen.next_u32() for _ in range(5000)]
    assert all(0 <= v < 2**32 for v in values)
    assert len(set(values)) > 4990
