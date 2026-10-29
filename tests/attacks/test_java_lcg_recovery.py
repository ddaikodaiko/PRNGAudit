# SPDX-License-Identifier: MIT
"""Nivel 5: recuperar `java.util.Random` con dos salidas, sobre vectores generados por el JDK."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from prng_audit.core.attacks.java_lcg_recovery import (
    MULTIPLIER_INV,
    clone,
    next_state,
    previous_state,
    recover_seed,
    recover_state_from_long,
    recover_states_from_ints,
)
from prng_audit.core.generators import ChaCha20Generator, JavaRandom
from prng_audit.core.generators.java_lcg import MASK48, MULTIPLIER

from _vectors import load_vectors

CASES: list[dict[str, Any]] = load_vectors("java_random.json")["cases"]
IDS = [f"seed={c['seed']}" for c in CASES]


def test_multiplier_inverse() -> None:
    assert (MULTIPLIER * MULTIPLIER_INV) & MASK48 == 1


@given(s=st.integers(0, MASK48))
def test_previous_state_undoes_next_state(s: int) -> None:
    assert previous_state(next_state(s)) == s
    assert next_state(previous_state(s)) == s


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_two_jdk_outputs_predict_the_remaining_9998(case: dict[str, Any]) -> None:
    """Las dos primeras salidas reales del JDK bastan para predecir todas las demás."""
    outputs: list[int] = case["next_int"]
    candidates = recover_states_from_ints(outputs[:2])
    assert len(candidates) >= 1
    # Si hubiera un falso positivo, la tercera salida lo descarta.
    (state,) = recover_states_from_ints(outputs[:3])
    gen = clone(state)
    assert [gen.next_int() for _ in outputs[3:]] == outputs[3:]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_recover_original_seed_low_48_bits(case: dict[str, Any]) -> None:
    (state,) = recover_states_from_ints(case["next_int"][:3])
    assert recover_seed(state, steps_back=3) == case["seed"] & MASK48


@pytest.mark.parametrize("offset", [1, 17, 500, 9000])
def test_recovery_mid_sequence(offset: int) -> None:
    outputs: list[int] = CASES[1]["next_int"]
    (state,) = recover_states_from_ints(outputs[offset : offset + 3])
    gen = clone(state)
    assert [gen.next_int() for _ in outputs[offset + 3 :]] == outputs[offset + 3 :]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_single_next_long_is_enough(case: dict[str, Any]) -> None:
    longs: list[int] = case["next_long"]
    gen = clone(recover_state_from_long(longs[0]))
    assert [gen.next_long() for _ in longs[1:]] == longs[1:]


def test_recovered_state_also_predicts_bounded_ints() -> None:
    """Con el estado, se predice cualquier método: por ejemplo, nextInt(37) de una ruleta."""
    victim = JavaRandom(123456789)
    (state,) = recover_states_from_ints([victim.next_int() for _ in range(3)])
    gen = clone(state)
    assert [gen.next_int(37) for _ in range(1000)] == [victim.next_int(37) for _ in range(1000)]


def test_rejects_single_output() -> None:
    with pytest.raises(ValueError, match="dos"):
        recover_states_from_ints([1])


def test_control_chacha20_outputs_have_no_consistent_lcg_state() -> None:
    """Grupo de control: con tres salidas de ChaCha20 no sobrevive ningún estado del LCG.

    La probabilidad de que un candidato sobreviva por azar a dos comprobaciones
    de 32 bits es ≈ 2¹⁶ · 2⁻⁶⁴ = 2⁻⁴⁸ por intento.
    """
    victim = ChaCha20Generator(5)
    for _ in range(20):
        outputs = [victim.next_u32() for _ in range(3)]
        assert recover_states_from_ints(outputs) == []
