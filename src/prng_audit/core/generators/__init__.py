# SPDX-License-Identifier: MIT
"""Generadores de números pseudoaleatorios con una interfaz común (`PRNG`)."""

from prng_audit.core.generators.base import PRNG, NotSupportedError
from prng_audit.core.generators.csprng import ChaCha20Generator, OsUrandomGenerator
from prng_audit.core.generators.java_lcg import JavaRandom
from prng_audit.core.generators.mt19937 import MT19937
from prng_audit.core.generators.xorshift128plus import XorShift128Plus

__all__ = [
    "MT19937",
    "PRNG",
    "ChaCha20Generator",
    "JavaRandom",
    "NotSupportedError",
    "OsUrandomGenerator",
    "XorShift128Plus",
]
