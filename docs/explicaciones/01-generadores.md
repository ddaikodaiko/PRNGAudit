# 01 · Generadores de números pseudoaleatorios

Módulo: `src/prng_audit/core/generators/` · Hito: H1

Este documento explica, en lenguaje llano, qué hace cada generador del
proyecto, por qué funciona como funciona, cómo se ha comprobado que es correcto
y qué preguntas puede hacer un tribunal.

---

## 1. Qué es un PRNG

Un generador de números pseudoaleatorios (PRNG) es una máquina de estados
**determinista** con tres piezas:

1. **Estado:** unos cuantos bits guardados en memoria.
2. **Transición:** una función que convierte el estado actual en el siguiente.
3. **Salida:** una función que, a partir del estado, produce el número que ve
   el usuario.

Con la misma semilla (el estado inicial), la secuencia es siempre la misma. Por
eso se llama *pseudo*aleatorio.

Hay dos formas muy distintas de que un PRNG sea "bueno":

| | Estadísticamente bueno | Criptográficamente seguro (CSPRNG) |
|---|---|---|
| Qué garantiza | Las salidas se distribuyen como si fueran aleatorias: frecuencias, rachas, correlaciones... | Sin conocer la clave, nadie puede predecir la siguiente salida mejor que tirando una moneda, aunque haya visto todas las anteriores |
| Ejemplo | Mersenne Twister | ChaCha20, `os.urandom` |
| Para qué sirve | Simulación, ciencia, videojuegos | Claves, tokens, **juegos con dinero** |

La tesis del proyecto es que la primera propiedad no implica la segunda. Este
hito construye los generadores; los hitos siguientes demuestran la tesis con
datos.

## 2. La interfaz común (`base.py`)

Todos los generadores heredan de `PRNG` y solo tienen que implementar cuatro
cosas: `next_u32()`, `seed()`, `getstate()` y `setstate()`. Las conversiones
se escriben una sola vez en la clase base:

- **`getrandbits(k)`** copia exactamente a CPython. Si k ≤ 32, toma **los k
  bits altos** de una palabra (`next_u32() >> (32 - k)`). Si k > 32, encadena
  palabras de la menos significativa a la más significativa.

  Por qué importa: si un juego hace `getrandbits(5)`, el jugador ve solo 5 de
  los 32 bits de cada salida. El ataque de salidas truncadas (nivel 3) necesita
  saber exactamente cuáles son esos bits.

- **`random()`** también copia a CPython: toma dos palabras, se queda con 27
  bits de la primera y 26 de la segunda, y forma un número de 53 bits (el
  tamaño de la mantisa de un `double`):

  ```
  a = next_u32() >> 5        # 27 bits
  b = next_u32() >> 6        # 26 bits
  random = (a·2²⁶ + b) / 2⁵³
  ```

  Consecuencia para el ataque de nivel 2: cada float filtra 53 de los 64 bits
  de dos salidas consecutivas.

  Los generadores que imitan a otra plataforma sobrescriben `random()` con la
  conversión de esa plataforma: `nextDouble()` en Java y `Math.random()` en V8.
  Así, en el casino simulado, "un juego hecho en Java" filtra exactamente lo
  que filtraría en Java.

- **`os.urandom` no tiene semilla ni estado** que se puedan leer. En lugar de
  devolver algo inventado, lanza `NotSupportedError`. Es una desviación
  deliberada de la interfaz: un CSPRNG del sistema no debe exponer su estado.

## 3. Mersenne Twister MT19937 (`mt19937.py`)

### 3.1 El estado

624 palabras de 32 bits (19 968 bits) más un índice `pos` que dice cuál es la
siguiente palabra a usar. De esos bits, solo 19 937 influyen en la secuencia:
del primer elemento solo se usa el bit alto, así que sobran 31 bits
(19 968 − 31 = 19 937). De ahí el nombre: el periodo es 2¹⁹⁹³⁷ − 1, que es un
primo de Mersenne.

### 3.2 La transición: el *twist*

Cuando se han gastado las 624 palabras, se regeneran todas:

```
para i = 0 … 623:
    y      = (bit alto de mt[i]) | (31 bits bajos de mt[i+1])
    mt[i]  = mt[i+397] ⊕ (y >> 1) ⊕ (0x9908B0DF si y es impar, si no 0)
```

Los índices son módulo 624. El vector se modifica sobre sí mismo, así que desde
i = 227 el término `mt[i+397]` ya es una palabra **nueva**. El código de
referencia lo hace así y hay que respetarlo para obtener la misma secuencia.

Todo son desplazamientos, XOR y una máscara condicionada a un bit: operaciones
**lineales sobre GF(2)** (el cuerpo de dos elementos, donde sumar es XOR). Esto
es la clave de los ataques del H5.

### 3.3 La salida: el *tempering*

Cada palabra del estado pasa por cuatro operaciones antes de salir:

```
y ^= y >> 11
y ^= (y << 7)  & 0x9D2C5680
y ^= (y << 15) & 0xEFC60000
y ^= y >> 18
```

Su objetivo es estadístico: mejorar la equidistribución de los bits. No aporta
ninguna seguridad, porque **cada paso es invertible**. En el H2 implementamos
`untemper`.

#### Ejemplo resuelto a mano: `temper(1)`

Escribimos las palabras en hexadecimal; cada dígito son 4 bits.

| Paso | Operación | Cálculo | y resultante |
|---|---|---|---|
| inicio | | | `0x00000001` |
| 1 | `y ^= y >> 11` | `1 >> 11 = 0`, así que no cambia | `0x00000001` |
| 2 | `y ^= (y << 7) & 0x9D2C5680` | `1 << 7 = 0x80`; el byte bajo de la máscara es `0x80`, que tiene ese bit a 1, así que el AND da `0x80` | `0x00000081` |
| 3 | `y ^= (y << 15) & 0xEFC60000` | `0x81 << 15 = 0x00408000` (bits 22 y 15). La máscara tiene el bit 22 a 1 (`0x00C60000` = bits 23, 22, 18, 17) y los 16 bits bajos a 0, así que el AND da `0x00400000` | `0x00400081` |
| 4 | `y ^= y >> 18` | `0x00400081 >> 18 = 0x10` (el bit 22 baja al bit 4) | `0x00400091` |

Resultado: `temper(1) = 0x00400091`. El test `test_temper_known_value`
comprueba este valor.

### 3.4 Dos formas de sembrar

| Rutina | Entrada | La usa |
|---|---|---|
| `init_genrand(s)` | un entero de 32 bits | `numpy.random.RandomState(s)`, `std::mt19937` de C++ |
| `init_by_array(key)` | una lista de palabras de 32 bits | `random.seed(n)` de CPython, que trocea \|n\| en palabras de 32 bits |

Por eso `random.Random(42)` y `numpy.random.RandomState(42)` dan secuencias
distintas aunque los dos sean MT19937 con "semilla 42": el algoritmo es el
mismo, pero el estado inicial no.

`MT19937.seed(n)` sigue a CPython, porque el casino simulado está escrito en
Python. Dos detalles heredados:

- `seed(-5)` da la misma secuencia que `seed(5)`, porque CPython usa el valor
  absoluto (test `test_negative_seed_equals_positive_seed_like_cpython`).
- `seed(None)` lee 624 palabras de `os.urandom` y las pasa a `init_by_array`,
  igual que CPython.

### 3.5 Cómo se ha validado

| Comprobación | Test |
|---|---|
| 10 000 salidas idénticas a `random.getrandbits(32)` con 9 semillas, desde 0 hasta 3²⁰⁰ y negativas | `test_seed_matches_cpython_getrandbits32` |
| 10 000 salidas idénticas a `RandomState` con `init_genrand` | `test_init_genrand_matches_numpy_randomstate` |
| Copiar el estado desde CPython en las posiciones 0, 1, 623, 624, 625 y 1500 (justo antes y después del twist) y seguir 10 000 salidas iguales | `test_state_from_cpython_mid_sequence` |
| El estado copiado en sentido contrario (nuestro → CPython, nuestro ↔ NumPy) | `test_state_to_cpython`, `test_state_roundtrip_with_numpy` |
| La salida número 10 000 con semilla 5489 vale 4123659995, el valor que exige el estándar de C++ | `test_reference_values_from_independent_sources` |
| `random()` y `getrandbits(k)` para k = 0…199 idénticos a CPython, y prueba de propiedad con hypothesis para semillas y k arbitrarios | `test_random_matches_cpython`, `test_getrandbits_*` |

## 4. `java.util.Random` (`java_lcg.py`)

Es un generador congruencial lineal (LCG) con un estado de 48 bits:

```
estado ← (estado · 0x5DEECE66D + 0xB) mod 2⁴⁸
next(bits) = los `bits` bits altos del nuevo estado
```

Al crearlo, la semilla se mezcla con `semilla ⊕ 0x5DEECE66D` y se recorta a 48
bits. `nextInt()` es `next(32)`, así que cada salida revela 32 de los 48 bits
del estado. Solo faltan 16 bits: hay 2¹⁶ = 65 536 candidatos, y una segunda
salida descarta todos menos uno. Es el ataque del H2 (nivel 5).

#### Ejemplo resuelto: `new Random(0).nextInt()`

1. Estado inicial: `0 ⊕ 0x5DEECE66D = 0x5DEECE66D`.
2. Un paso: `(0x5DEECE66D · 0x5DEECE66D + 0xB) mod 2⁴⁸ = 0xBB20B4600A74`.
3. Salida: los 32 bits altos, `0xBB20B4600A74 >> 16 = 0xBB20B460` = 3 139 482 720.
4. Como `int` de Java (con signo): 3 139 482 720 − 2³² = **−1 155 484 576**.

Es el mismo valor que imprime el JDK (primer elemento de
`tests/vectors/data/java_random.json`).

`nextInt(bound)` usa **muestreo con rechazo**: si el valor cae en el último
tramo incompleto, lo descarta y pide otro. Así evita el sesgo, pero consume
salidas que el jugador no ve. Ese es justo el problema del nivel abierto 7.

**Validación:** un programa Java (`tests/vectors/GenJavaVectors.java`) genera,
con 6 semillas (incluidas 0, −1 y `Long.MIN_VALUE`), 10 000 `nextInt()` y 1 000
valores de cada uno de los siguientes: `nextInt(bound)` con 9 cotas,
`nextLong()`, `nextDouble()` y `nextFloat()`. Los doubles y floats se comparan
**bit a bit**.

## 5. xorshift128+ y `Math.random()` de V8 (`xorshift128plus.py`)

Estado: dos palabras de 64 bits, `s0` y `s1`. Un paso:

```
x = s0;  y = s1
s0 = y
x ^= x << 23;  x ^= x >> 17;  x ^= y;  x ^= y >> 26
s1 = x
salida canónica = s0 + s1  (mod 2⁶⁴)
```

Todo es lineal sobre GF(2) excepto la suma final. Además, el bit más bajo de
una suma es el XOR de los bits más bajos, así que también es lineal. Por eso
`next_u32()` devuelve los 32 bits altos, que son los de mejor calidad.

### Cómo lo usa V8 en `Math.random()`

Al leer el código fuente de V8 encontramos dos detalles que no aparecen en
ninguna descripción general, y los dos importan para el ataque del H5:

1. **Siembra:** `s0 = MurmurHash3(seed)` y `s1 = MurmurHash3(~seed)`.
2. **Caché LIFO** (V8 de Node 22): `Math.random()` no da un paso por llamada.
   Calcula 64 pasos de golpe, guarda `ToDouble(s0)` de cada uno (los 52 bits
   altos de `s0` como mantisa) y los entrega **del último al primero**. Un
   atacante que observa `Math.random()` ve la secuencia invertida por bloques
   de 64 y tiene que reordenarla antes de resolver el sistema.

En la rama principal actual de V8 esto ha cambiado en 64 bits: ya no hay caché
y cada llamada devuelve los 53 bits altos de `s0 + s1`. Implementamos los dos
perfiles:

| Perfil | Descripción | Validado contra un binario |
|---|---|---|
| `"v8-cache"` | Node 22 (V8 12.4) | Sí: 10 000 valores × 5 semillas contra `node --random-seed=N`, comparados bit a bit |
| `"v8-direct"` | Rama principal de V8 | **No**: transcrito del código fuente. La versión exacta de V8 en que cambió está pendiente de verificar (TODO-VERIFICAR) |

**Validación de la salida canónica:** un programa en C
(`tests/vectors/xorshift128plus_ref.c`) con `uint64_t`, que desborda de forma
natural, genera 10 000 salidas con 5 semillas. Así se comprueba que las
máscaras de 64 bits de Python reproducen la aritmética de C.

## 6. Los CSPRNG (`csprng.py`)

- **`OsUrandomGenerator`** lee de `os.urandom`, la misma fuente que `secrets` y
  `random.SystemRandom`. No tiene semilla ni estado observable.
- **`ChaCha20Generator`** produce el flujo de clave de ChaCha20 (RFC 8439) con
  la librería `cryptography` y lo corta en palabras de 32 bits little-endian.
  Es determinista a partir de la clave, así que los experimentos se pueden
  repetir. Su seguridad no viene de ser impredecible "por naturaleza", sino de
  que sin la clave de 256 bits nadie puede reconstruir el estado.

  **Advertencia** (está en el código): `ChaCha20Generator(seed)` deriva la
  clave con SHA-256 de la semilla. Eso **no añade entropía**: con una semilla
  de 32 bits, la clave solo tiene 2³² posibilidades y se puede buscar por
  fuerza bruta. Un buen algoritmo con una mala semilla sigue siendo un mal
  sistema. Este caso lo modelará el casino simulado en el H4.

**Validación:** dos vectores oficiales del RFC 8439 (§2.3.2 y apéndice A.1
n.º 1) comparados byte a byte. También se comprueba que saltar a cualquier
posición del flujo, incluidos los bordes del búfer interno de 4 KiB, da lo
mismo que avanzar palabra a palabra.

## 7. Qué está verificado y qué no

| Afirmación | Evidencia |
|---|---|
| MT19937 idéntico a CPython y NumPy | Tests con 10 000 salidas y transferencia de estado |
| LCG idéntico a `java.util.Random` | Vectores de OpenJDK 21 (local) y Temurin 21 (CI) |
| `Math.random()` de Node 22 reproducido exactamente | Vectores de Node 22.22.0 / V8 12.4 |
| Perfil `v8-direct` | Solo transcripción del código fuente (pendiente) |
| ChaCha20 correcto | Vectores del RFC 8439 |

La CI regenera los vectores de Java, V8 y C con las herramientas reales y los
compara con los versionados (`make vectors-check`). Si una versión futura de
Java o de Node cambiara el algoritmo, la CI fallaría.

---

## 8. Preguntas probables del tribunal

**¿Por qué implementar el MT desde cero si Python ya lo trae?**
Porque el de CPython está escrito en C y no expone el twist ni el tempering por
separado, y los ataques necesitan manipular el estado paso a paso. Además, para
defender el trabajo hay que poder explicar cada línea. La implementación propia
se valida contra la de CPython, no la sustituye.

**¿Cómo sabes que tu implementación es correcta? ¿10 000 salidas iguales lo
demuestran?**
No es una demostración formal, pero la evidencia es fuerte por tres motivos:

- El generador es determinista y cada salida depende de todo el estado. Un
  error en el twist aparece como muy tarde en la salida 625; 10 000 salidas
  recorren 16 twists completos.
- El estado se transfiere en posiciones críticas (0, 623, 624, 625...) en los
  dos sentidos y con dos implementaciones independientes, CPython y NumPy.
- Hay un valor publicado que no depende de Python: el estándar de C++ exige que
  la salida número 10 000 sea 4123659995.

**¿Por qué `random.Random(42)` y `RandomState(42)` no dan lo mismo?**
Porque siembran con rutinas distintas: CPython con `init_by_array` y NumPy con
`init_genrand`. El algoritmo es el mismo; el estado inicial no.

**¿Por qué `random()` gasta dos salidas de 32 bits?**
Porque un `double` tiene 53 bits de mantisa y una salida solo aporta 32. CPython
toma 27 + 26 = 53 bits.

**¿Entonces el Mersenne Twister es un mal generador?**
No. Estadísticamente es excelente y por eso es el generador por defecto de
tantos lenguajes. El problema es usarlo donde importa que nadie pueda
predecirlo. Esa es exactamente la tesis del proyecto.

**¿Por qué basta con dos salidas para romper el LCG de Java?**
Una salida de `nextInt()` revela 32 de los 48 bits del estado. Faltan 16 bits,
es decir, 65 536 posibilidades, y una segunda salida deja una sola.

**¿Por qué importa el orden de la caché de V8?**
Porque un atacante que observa `Math.random()` no ve los pasos del generador en
orden: los ve al revés dentro de cada bloque de 64. Si se plantea el sistema de
ecuaciones con el orden equivocado, no tiene solución.

**¿Cómo puede ser seguro un CSPRNG determinista como ChaCha20 sembrado?**
La seguridad no viene del indeterminismo, sino de que la clave sea secreta y
tenga suficiente entropía. Con una clave de 256 bits aleatorios es seguro; con
una clave derivada de una semilla de 32 bits, no.

**¿Por qué `next_u32()` de xorshift128+ toma los bits altos?**
Porque los bits bajos de una suma tienen peor calidad: el más bajo es el XOR
de los dos bits más bajos y, por tanto, es completamente lineal.

## Referencias

- Matsumoto, M. y Nishimura, T. (1998). *Mersenne Twister: a 623-dimensionally
  equidistributed uniform pseudo-random number generator*. ACM TOMACS 8(1).
- Marsaglia, G. (2003). *Xorshift RNGs*. Journal of Statistical Software 8(14).
- Vigna, S. (2017). *Further scramblings of Marsaglia's xorshift generators*.
  Journal of Computational and Applied Mathematics 315.
- Nir, Y. y Langley, A. (2018). *ChaCha20 and Poly1305 for IETF Protocols*.
  RFC 8439.
- Documentación de la clase `java.util.Random` (Java SE 21).
- Código fuente de V8, consultado el 2026-10-29 en `github.com/v8/v8`:
  `src/base/utils/random-number-generator.h`, `src/numbers/math-random.cc` y
  `src/builtins/math.tq`.

Las referencias bibliográficas se cotejarán con su DOI en el H9; véase
`paper/referencias.bib`.
