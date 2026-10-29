# SPDX-License-Identifier: MIT
"""Propiedades que debe cumplir cualquier generador de la interfaz común."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from prng_audit.core.generators import (
    MT19937,
    PRNG,
    ChaCha20Generator,
    JavaRandom,
    OsUrandomGenerator,
    XorShift128Plus,
)

SEEDABLE: dict[str, Callable[[int], PRNG[Any]]] = {
    "mt19937": MT19937,
    "java_lcg": JavaRandom,
    "xorshift128plus": XorShift128Plus,
    "xorshift128plus-direct": lambda s: XorShift128Plus(s, profile="v8-direct"),
    "chacha20": ChaCha20Generator,
}
ALL: dict[str, Callable[[int], PRNG[Any]]] = {
    **SEEDABLE,
    "os_urandom": lambda _s: OsUrandomGenerator(),
}


@pytest.mark.parametrize("factory", SEEDABLE.values(), ids=SEEDABLE.keys())
@settings(max_examples=25, deadline=None)
@given(seed=st.integers(-(2**63), 2**63 - 1), steps=st.integers(0, 700))
def test_getstate_setstate_roundtrip(
    factory: Callable[[int], PRNG[Any]], seed: int, steps: int
) -> None:
    gen = factory(seed)
    for _ in range(steps):
        gen.next_u32()
    clone = factory(seed + 1)
    clone.setstate(gen.getstate())
    assert [clone.next_u32() for _ in range(50)] == [gen.next_u32() for _ in range(50)]
    assert [clone.random() for _ in range(5)] == [gen.random() for _ in range(5)]


@pytest.mark.parametrize("factory", SEEDABLE.values(), ids=SEEDABLE.keys())
def test_same_seed_same_sequence_different_seed_different_sequence(
    factory: Callable[[int], PRNG[Any]],
) -> None:
    a, b, c = factory(1), factory(1), factory(2)
    seq_a = [a.next_u32() for _ in range(100)]
    assert seq_a == [b.next_u32() for _ in range(100)]
    assert seq_a != [c.next_u32() for _ in range(100)]


@pytest.mark.parametrize("factory", ALL.values(), ids=ALL.keys())
@settings(max_examples=25, deadline=None)
@given(k=st.integers(0, 200))
def test_output_ranges(factory: Callable[[int], PRNG[Any]], k: int) -> None:
    gen = factory(5)
    assert 0 <= gen.next_u32() < 2**32
    assert 0 <= gen.getrandbits(k) < 2**k or k == 0
    x = gen.random()
    assert 0.0 <= x < 1.0


@pytest.mark.parametrize("factory", ALL.values(), ids=ALL.keys())
def test_negative_bits_rejected(factory: Callable[[int], PRNG[Any]]) -> None:
    with pytest.raises(ValueError, match="negativo"):
        factory(0).getrandbits(-1)
