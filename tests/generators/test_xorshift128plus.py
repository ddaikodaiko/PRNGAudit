# SPDX-License-Identifier: MIT
"""xorshift128+ contra la referencia en C y `Math.random()` de V8 contra Node real."""

from __future__ import annotations

import struct
from typing import Any

import pytest

from prng_audit.core.generators.xorshift128plus import (
    V8_CACHE_SIZE,
    XorShift128Plus,
    XorShiftState,
    murmurhash3_fmix64,
    xorshift128_step,
)

from _vectors import load_vectors

C_CASES: list[dict[str, Any]] = load_vectors("xorshift128plus.json")["cases"]
V8_CASES: list[dict[str, Any]] = load_vectors("v8_math_random.json")["cases"]


def double_from_hex(bits: str) -> float:
    value: float = struct.unpack("<d", struct.pack("<Q", int(bits, 16)))[0]
    return value


@pytest.mark.parametrize("case", C_CASES, ids=[f"seed={c['seed']}" for c in C_CASES])
def test_next_u64_matches_c_reference(case: dict[str, Any]) -> None:
    gen = XorShift128Plus(case["seed"])
    expected = [int(x, 16) for x in case["next_u64"]]
    assert len(expected) == 10_000
    assert [gen.next_u64() for _ in expected] == expected


@pytest.mark.parametrize("case", V8_CASES, ids=[f"seed={c['seed']}" for c in V8_CASES])
def test_math_random_matches_node(case: dict[str, Any]) -> None:
    """10 000 valores = 156 recargas completas de la caché de 64 y una parcial."""
    gen = XorShift128Plus(case["seed"], profile="v8-cache")
    expected = [double_from_hex(b) for b in case["math_random_bits"]]
    assert len(expected) == 10_000
    assert [gen.random() for _ in expected] == expected


def test_v8_cache_is_served_lifo() -> None:
    """El primer valor de Math.random() sale del ÚLTIMO paso de un bloque de 64."""
    gen = XorShift128Plus(42, profile="v8-cache")
    first = gen.random()
    s0, s1 = murmurhash3_fmix64(42), murmurhash3_fmix64(~42 & (2**64 - 1))
    for _ in range(V8_CACHE_SIZE):
        s0, s1 = xorshift128_step(s0, s1)
    assert first == ((s0 >> 12) / 2**52)


def test_v8_direct_profile_uses_top_53_bits_of_sum() -> None:
    a = XorShift128Plus(7, profile="v8-direct")
    b = XorShift128Plus(7)
    for _ in range(1000):
        assert a.random() == (b.next_u64() >> 11) / 2**53


def test_next_u32_is_high_half_of_u64() -> None:
    a, b = XorShift128Plus(3), XorShift128Plus(3)
    for _ in range(1000):
        assert a.next_u32() == b.next_u64() >> 32


@pytest.mark.parametrize("advance", [0, 1, 63, 64, 65, 200])
def test_state_roundtrip_mid_cache(advance: int) -> None:
    gen = XorShift128Plus(11)
    for _ in range(advance):
        gen.random()
    clone = XorShift128Plus(0)
    clone.setstate(gen.getstate())
    assert [clone.random() for _ in range(300)] == [gen.random() for _ in range(300)]


def test_invalid_state_and_profile() -> None:
    with pytest.raises(ValueError, match="prohibido"):
        XorShift128Plus().setstate(XorShiftState(0, 0))
    with pytest.raises(ValueError, match="perfil"):
        XorShift128Plus(1, profile="v9")  # type: ignore[arg-type]
