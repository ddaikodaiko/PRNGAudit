# SPDX-License-Identifier: MIT
"""Equivalencia de `JavaRandom` con `java.util.Random` del JDK (vectores generados con Java)."""

from __future__ import annotations

import struct
from typing import Any

import pytest

from prng_audit.core.generators.java_lcg import MASK48, JavaRandom, scramble, to_int32

from _vectors import load_vectors

CASES: list[dict[str, Any]] = load_vectors("java_random.json")["cases"]
IDS = [f"seed={c['seed']}" for c in CASES]


def double_bits(x: float) -> int:
    """Bits de un double como `long` de Java (con signo)."""
    u: int = struct.unpack("<q", struct.pack("<d", x))[0]
    return u


def float_bits(x: float) -> int:
    u: int = struct.unpack("<i", struct.pack("<f", x))[0]
    return u


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_next_int_matches_jdk(case: dict[str, Any]) -> None:
    r = JavaRandom(case["seed"])
    expected = case["next_int"]
    assert len(expected) == 10_000
    assert [r.next_int() for _ in expected] == expected


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_next_int_bound_matches_jdk(case: dict[str, Any]) -> None:
    for bound, expected in case["next_int_bound"].items():
        r = JavaRandom(case["seed"])
        assert [r.next_int(int(bound)) for _ in expected] == expected, bound


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_next_long_matches_jdk(case: dict[str, Any]) -> None:
    r = JavaRandom(case["seed"])
    assert [r.next_long() for _ in case["next_long"]] == case["next_long"]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_next_double_and_random_match_jdk(case: dict[str, Any]) -> None:
    expected = case["next_double_bits"]
    r = JavaRandom(case["seed"])
    assert [double_bits(r.next_double()) for _ in expected] == expected
    r = JavaRandom(case["seed"])
    assert [double_bits(r.random()) for _ in expected] == expected


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_next_float_matches_jdk(case: dict[str, Any]) -> None:
    r = JavaRandom(case["seed"])
    expected = case["next_float_bits"]
    assert [float_bits(r.next_float()) for _ in expected] == expected


def test_next_u32_is_unsigned_next_int() -> None:
    a, b = JavaRandom(5), JavaRandom(5)
    for _ in range(1000):
        assert to_int32(a.next_u32()) == b.next_int()


def test_state_is_scrambled_seed_and_roundtrips() -> None:
    r = JavaRandom(42)
    assert r.getstate() == scramble(42) == (42 ^ 0x5DEECE66D) & MASK48
    for _ in range(17):
        r.next_int()
    clone = JavaRandom()
    clone.setstate(r.getstate())
    assert [clone.next_int() for _ in range(100)] == [r.next_int() for _ in range(100)]


def test_invalid_arguments() -> None:
    r = JavaRandom(1)
    with pytest.raises(ValueError, match="positivo"):
        r.next_int(0)
    with pytest.raises(ValueError, match="bits"):
        r.next_bits(33)
    with pytest.raises(ValueError, match="48 bits"):
        r.setstate(1 << 48)
