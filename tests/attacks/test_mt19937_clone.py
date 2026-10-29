# SPDX-License-Identifier: MIT
"""Nivel 1: untemper y clonado del MT19937 a partir de 624 salidas completas."""

from __future__ import annotations

import random

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from prng_audit.core.attacks.mt19937_clone import (
    clone,
    prediction_accuracy,
    recover_state,
    temper_array,
    untemper,
    untemper_array,
)
from prng_audit.core.generators import ChaCha20Generator
from prng_audit.core.generators.mt19937 import N, temper, to_cpython_state

U32 = st.integers(min_value=0, max_value=2**32 - 1)
N_PREDICT = 10_000


# --- untemper ---------------------------------------------------------------


def test_untemper_worked_example() -> None:
    """El ejemplo resuelto a mano en docs/explicaciones/02-ataques-mt-y-lcg.md."""
    assert untemper(0x00400091) == 1


@given(x=U32)
def test_untemper_inverts_temper(x: int) -> None:
    assert untemper(temper(x)) == x
    assert temper(untemper(x)) == x


@given(a=U32, b=U32)
def test_temper_and_untemper_are_linear_over_gf2(a: int, b: int) -> None:
    """f(a ⊕ b) = f(a) ⊕ f(b): solo usan XOR, desplazamientos y AND con constantes."""
    assert temper(a ^ b) == temper(a) ^ temper(b)
    assert untemper(a ^ b) == untemper(a) ^ untemper(b)


def test_untemper_on_basis_vectors() -> None:
    """Con la linealidad, comprobar los 32 vectores de la base demuestra el caso general.

    Todo x de 32 bits es un XOR de vectores e_i = 1 << i. Si untemper∘temper es
    lineal y deja fijos todos los e_i, deja fijo cualquier x.
    """
    for i in range(32):
        assert untemper(temper(1 << i)) == 1 << i
    assert untemper(temper(0)) == 0


@given(xs=st.lists(U32, min_size=1, max_size=200))
def test_array_versions_match_scalar(xs: list[int]) -> None:
    arr = np.array(xs, dtype=np.uint32)
    assert [int(v) for v in temper_array(arr)] == [temper(x) for x in xs]
    assert [int(v) for v in untemper_array(arr)] == [untemper(x) for x in xs]


@pytest.mark.slow
def test_untemper_exhaustive_all_2_32_values() -> None:
    """Los 4 294 967 296 valores posibles, por bloques de 2²⁴ (varios minutos)."""
    chunk = 1 << 24
    for start in range(0, 1 << 32, chunk):
        x = np.arange(start, start + chunk, dtype=np.uint64).astype(np.uint32)
        assert np.array_equal(untemper_array(temper_array(x)), x), hex(start)


# --- Clonado ----------------------------------------------------------------


def observe(victim: random.Random, n: int) -> list[int]:
    return [victim.getrandbits(32) for _ in range(n)]


@pytest.mark.parametrize("seed", [0, 42, 2**64 + 1, -31337])
@pytest.mark.parametrize("offset", [0, 1, 300, 623, 624, 1000])
def test_clone_predicts_next_10000_outputs_of_cpython(seed: int, offset: int) -> None:
    """Criterio del hito: 100 % de aciertos en las 10 000 salidas siguientes.

    `offset` desplaza el inicio de la observación respecto a los twists de la
    víctima, para demostrar que el alineamiento no importa.
    """
    victim = random.Random(seed)
    observe(victim, offset)
    cloned = clone(observe(victim, N))
    predicted = [cloned.next_u32() for _ in range(N_PREDICT)]
    actual = observe(victim, N_PREDICT)
    assert prediction_accuracy(predicted, actual) == 1.0


def test_cloned_state_drives_cpython_random_functions() -> None:
    """Con el estado clonado, el propio `random` de Python predice randint, shuffle y choice."""
    victim = random.Random(2026)
    cloned = random.Random()
    cloned.setstate(to_cpython_state(recover_state(observe(victim, N))))

    assert [cloned.random() for _ in range(100)] == [victim.random() for _ in range(100)]
    assert [cloned.randint(0, 36) for _ in range(100)] == [
        victim.randint(0, 36) for _ in range(100)
    ]
    deck_a, deck_b = list(range(52)), list(range(52))
    cloned.shuffle(deck_a)
    victim.shuffle(deck_b)
    assert deck_a == deck_b
    assert cloned.choice("abcdef") == victim.choice("abcdef")


def test_clone_numpy_randomstate() -> None:
    victim = np.random.RandomState(7)
    obs = [int(x) for x in victim.randint(0, 2**32, size=N, dtype=np.uint32)]
    cloned = clone(obs)
    actual = [int(x) for x in victim.randint(0, 2**32, size=N_PREDICT, dtype=np.uint32)]
    assert [cloned.next_u32() for _ in range(N_PREDICT)] == actual


def test_extra_observations_use_the_last_624() -> None:
    victim = random.Random(5)
    cloned = clone(observe(victim, 2000))
    assert [cloned.next_u32() for _ in range(100)] == observe(victim, 100)


def test_rejects_too_few_or_invalid_outputs() -> None:
    with pytest.raises(ValueError, match="624"):
        recover_state([0] * (N - 1))
    with pytest.raises(ValueError, match="32 bits"):
        recover_state([2**32] * N)


def test_control_chacha20_cannot_be_cloned() -> None:
    """Grupo de control: el mismo ataque sobre ChaCha20 no acierta por encima del azar."""
    victim = ChaCha20Generator(1)
    cloned = clone([victim.next_u32() for _ in range(N)])
    predicted = [cloned.next_u32() for _ in range(N_PREDICT)]
    actual = [victim.next_u32() for _ in range(N_PREDICT)]
    # Al azar, la probabilidad de acertar una palabra es 2⁻³².
    assert prediction_accuracy(predicted, actual) == 0.0
