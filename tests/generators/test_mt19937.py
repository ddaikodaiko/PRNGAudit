# SPDX-License-Identifier: MIT
"""Equivalencia de MT19937 con CPython (`random`) y NumPy (`RandomState`)."""

from __future__ import annotations

import random

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from prng_audit.core.generators.mt19937 import (
    MT19937,
    MTState,
    N,
    from_cpython_state,
    from_numpy_state,
    temper,
    to_cpython_state,
    to_numpy_state,
)

N_OUT = 10_000

CPYTHON_SEEDS = [0, 1, 42, 5489, 2**32 - 1, 2**32, 2**64 + 12345, -987654321, 3**200]
GENRAND_SEEDS = [0, 1, 42, 5489, 2**32 - 1]


def numpy_u32(rs: np.random.RandomState, n: int) -> list[int]:
    """n palabras de 32 bits (con rango completo, randint consume una salida por valor)."""
    return [int(x) for x in rs.randint(0, 2**32, size=n, dtype=np.uint32)]


@pytest.mark.parametrize("seed", CPYTHON_SEEDS)
def test_seed_matches_cpython_getrandbits32(seed: int) -> None:
    ours = MT19937(seed)
    ref = random.Random(seed)
    assert [ours.next_u32() for _ in range(N_OUT)] == [ref.getrandbits(32) for _ in range(N_OUT)]


@pytest.mark.parametrize("seed", GENRAND_SEEDS)
def test_init_genrand_matches_numpy_randomstate(seed: int) -> None:
    ours = MT19937()
    ours.init_genrand(seed)
    ref = np.random.RandomState(seed)
    assert [ours.next_u32() for _ in range(N_OUT)] == numpy_u32(ref, N_OUT)


def test_reference_values_from_independent_sources() -> None:
    """Valores publicados que no dependen de Python.

    - 3499211612: primera salida de `init_genrand(5489)` (semilla por defecto
      del código de referencia `mt19937ar.c`).
    - 4123659995: el estándar de C++ (ISO/IEC 14882, [rand.predef]) exige que
      la salida número 10 000 de un `std::mt19937` construido por defecto
      (semilla 5489) sea exactamente este valor.
    """
    gen = MT19937()
    gen.init_genrand(5489)
    outputs = [gen.next_u32() for _ in range(10_000)]
    assert outputs[0] == 3499211612
    assert outputs[-1] == 4123659995


@pytest.mark.parametrize("seed", [7, 2**40 + 3])
@pytest.mark.parametrize("advance", [0, 1, 623, 624, 625, 1500])
def test_state_from_cpython_mid_sequence(seed: int, advance: int) -> None:
    """Copiar el estado de CPython en cualquier punto (también justo antes y después del twist)."""
    ref = random.Random(seed)
    for _ in range(advance):
        ref.getrandbits(32)
    ours = MT19937()
    ours.setstate(from_cpython_state(ref.getstate()))
    assert [ours.next_u32() for _ in range(N_OUT)] == [ref.getrandbits(32) for _ in range(N_OUT)]


def test_state_to_cpython() -> None:
    ours = MT19937(2024)
    for _ in range(1000):
        ours.next_u32()
    ref = random.Random()
    ref.setstate(to_cpython_state(ours.getstate()))
    assert [ref.getrandbits(32) for _ in range(N_OUT)] == [ours.next_u32() for _ in range(N_OUT)]


@pytest.mark.parametrize("advance", [0, 100, 624, 1000])
def test_state_roundtrip_with_numpy(advance: int) -> None:
    ref = np.random.RandomState(31337)
    numpy_u32(ref, advance)
    ours = MT19937()
    ours.setstate(from_numpy_state(ref.get_state()))
    assert [ours.next_u32() for _ in range(N_OUT)] == numpy_u32(ref, N_OUT)

    ref2 = np.random.RandomState()
    ref2.set_state(to_numpy_state(ours.getstate()))
    assert numpy_u32(ref2, N_OUT) == [ours.next_u32() for _ in range(N_OUT)]


@pytest.mark.parametrize("seed", [0, 42, 2**70])
def test_random_matches_cpython(seed: int) -> None:
    ours = MT19937(seed)
    ref = random.Random(seed)
    assert [ours.random() for _ in range(N_OUT)] == [ref.random() for _ in range(N_OUT)]


def test_getrandbits_matches_cpython_for_all_small_k() -> None:
    ours = MT19937(99)
    ref = random.Random(99)
    for k in range(0, 200):
        for _ in range(20):
            assert ours.getrandbits(k) == ref.getrandbits(k), k


@given(seed=st.integers(min_value=-(2**300), max_value=2**300), k=st.integers(0, 300))
def test_getrandbits_matches_cpython_property(seed: int, k: int) -> None:
    ours = MT19937(seed)
    ref = random.Random(seed)
    assert [ours.getrandbits(k) for _ in range(3)] == [ref.getrandbits(k) for _ in range(3)]


def test_seed_none_uses_entropy() -> None:
    a, b = MT19937(), MT19937()
    assert [a.next_u32() for _ in range(4)] != [b.next_u32() for _ in range(4)]


def test_temper_known_value() -> None:
    """Ejemplo resuelto a mano en docs/explicaciones/01-generadores.md."""
    assert temper(1) == 0x00400091
    assert temper(0) == 0


def test_state_validation() -> None:
    with pytest.raises(ValueError, match="624"):
        MTState(words=(0,) * 10, pos=0)
    with pytest.raises(ValueError, match="posición"):
        MTState(words=(0,) * N, pos=625)
    with pytest.raises(ValueError, match="32 bits"):
        MTState(words=(2**32,) + (0,) * (N - 1), pos=0)
    with pytest.raises(ValueError, match="vacía"):
        MT19937().init_by_array([])


def test_negative_seed_equals_positive_seed_like_cpython() -> None:
    """CPython siembra con |n|: `seed(-5)` y `seed(5)` dan la misma secuencia."""
    assert [MT19937(-5).next_u32() for _ in range(10)] == [MT19937(5).next_u32() for _ in range(10)]
    assert random.Random(-5).random() == random.Random(5).random()
