# prng-audit

**Auditoría criptográfica de generadores de números pseudoaleatorios (PRNG) y teoría de juegos.**

> [!WARNING]
> **Proyecto educativo y de investigación.** Todos los ataques se ejecutan
> exclusivamente contra el casino simulado de este repositorio o contra
> generadores instanciados en local. El proyecto no contiene ni contendrá
> código que se conecte, haga *scraping* o interactúe con plataformas de juego
> reales, ni guías para hacerlo.
>
> Las plataformas de juego reguladas usan generadores certificados por
> laboratorios independientes (por ejemplo, según el estándar GLI-19). La
> conclusión de este trabajo es **"así falla un sistema mal implementado"**,
> no "los casinos son vulnerables".

> [!NOTE]
> **Juego responsable.** El juego con dinero real tiene una esperanza negativa
> para el jugador y puede generar adicción. Si el juego te está causando
> problemas a ti o a alguien cercano, busca ayuda. En España: www.jugarbien.es
> (Dirección General de Ordenación del Juego).

## Pregunta de investigación

¿Cómo se puede predecir un generador lineal como el Mersenne Twister (el de
serie en Python, PHP, Ruby, R o MATLAB) a partir de suficientes salidas
consecutivas, en comparación con un generador criptográficamente seguro? ¿Y
cuánta ventaja da esa predicción a un jugador?

**Tesis:** un generador puede pasar las pruebas estadísticas de aleatoriedad y
aun así ser completamente predecible. Pasar los tests no implica seguridad.

## Estado

| Hito | Contenido | Estado |
|---|---|---|
| H1 | Esqueleto, CI, generadores validados contra CPython, NumPy, JDK y V8 | ✅ |
| H2 | Ataques: MT con salidas completas y LCG de Java | ✅ |
| H3 | Batería NIST SP 800-22 | ⏳ |
| H4 | Casino simulado | ⏳ |
| H5 | Ataques: floats, salidas truncadas (GF(2)), semilla por tiempo, xorshift128+ | ⏳ |
| H6 | Kelly, árboles de decisión y Monte Carlo | ⏳ |
| H7 | API con streaming | ⏳ |
| H8 | App PWA | ⏳ |
| H9 | Experimentos y manuscrito | ⏳ |
| H10 | Muestreo con rechazo, informe de auditoría y release | ⏳ |

## Generadores incluidos

| Generador | Módulo | Validado contra |
|---|---|---|
| MT19937 | `prng_audit.core.generators.mt19937` | `random` de CPython, `numpy.random.RandomState`, valor de referencia del estándar C++ |
| `java.util.Random` (LCG de 48 bits) | `prng_audit.core.generators.java_lcg` | OpenJDK 21 |
| xorshift128+ y `Math.random()` de V8 | `prng_audit.core.generators.xorshift128plus` | Referencia en C y Node 22 (V8 12.4) |
| `os.urandom` | `prng_audit.core.generators.csprng` | — (grupo de control) |
| ChaCha20 | `prng_audit.core.generators.csprng` | Vectores del RFC 8439 |

La explicación de cada uno, en lenguaje llano, está en
[`docs/explicaciones/01-generadores.md`](docs/explicaciones/01-generadores.md).

## Resultados hasta ahora

| Ataque | Observaciones | Acierto en las 10 000 salidas siguientes | Control (ChaCha20, `os.urandom`) |
|---|---:|---:|---:|
| Nivel 1: clonar MT19937 (`random` de Python) | 624 salidas de 32 bits | 100 % (100/100 ensayos) | 0 % |
| Nivel 5: recuperar `java.util.Random` | 2 `nextInt()` | 100 % (100/100 ensayos) | 0 estados compatibles |

Explicación: [`docs/explicaciones/02-ataques-mt-y-lcg.md`](docs/explicaciones/02-ataques-mt-y-lcg.md).
Reproducir: `make experiments` (resultados en `experiments/out/`).

## Uso rápido

Requisitos: [uv](https://docs.astral.sh/uv/) (instala Python 3.12 si hace falta).

```bash
make install    # uv sync --frozen
make check      # ruff + mypy + pytest
```

```python
from prng_audit.core.generators import MT19937
import random

g = MT19937(42)
r = random.Random(42)
assert g.getrandbits(32) == r.getrandbits(32)
```

Ejemplo de clonado del Mersenne Twister de Python a partir de 624 salidas:

```python
import random
from prng_audit.core.attacks.mt19937_clone import clone

victima = random.Random()                      # semilla desconocida
observadas = [victima.getrandbits(32) for _ in range(624)]
clon = clone(observadas)
assert clon.getrandbits(32) == victima.getrandbits(32)
```

Para regenerar los vectores de referencia hace falta además un JDK, Node 22 y
un compilador de C: `make vectors-check`.

## Estructura

```
src/prng_audit/
  core/generators/   generadores con interfaz común
  core/attacks/      ataques (H2, H5, H10)
  core/stats/        batería estadística (H3)
  core/games/        casino simulado (H4)
  core/strategy/     Kelly y árboles de decisión (H6)
  sim/               Monte Carlo concurrente (H6)
  api/               FastAPI (H7)
web/                 app React + TypeScript, PWA (H8)
experiments/         un script por experimento (H9)
paper/               manuscrito y bibliografía (H9)
docs/adr/            decisiones de arquitectura
docs/explicaciones/  un documento por módulo, para la defensa
tests/               pytest + hypothesis; vectores de referencia en tests/vectors/
```

## Licencia

[MIT](LICENSE). Véase [ADR 0003](docs/adr/0003-licencia-mit.md).
