# 02 · Ataques de nivel 1 y 5: clonar el Mersenne Twister y el LCG de Java

Módulos: `src/prng_audit/core/attacks/mt19937_clone.py` y
`src/prng_audit/core/attacks/java_lcg_recovery.py` · Hito: H2

Experimentos: `experiments/e01_mt_full_outputs.py` y
`experiments/e05_java_lcg.py` (`make experiments`).

---

## 1. Qué se demuestra en este hito

Dos generadores que pasan sin problema las pruebas estadísticas habituales
(lo mediremos en el H3) son **completamente predecibles** si el atacante ve
sus salidas en bruto:

| Generador | Salidas observadas | Acierto en las siguientes | Tiempo de ataque (mediana) |
|---|---:|---:|---:|
| MT19937 (`random` de Python) | 624 de 32 bits | 100 % de 10 000, en 100 de 100 ensayos | ≈ 1–2 ms |
| `java.util.Random` | 2 de `nextInt()` | 100 % de 10 000, en 100 de 100 ensayos | ≈ 20 ms |
| ChaCha20, `os.urandom` (control) | las mismas | 0 % | — |

Las cifras salen de `experiments/out/e01_mt_full_outputs.md` y
`experiments/out/e05_java_lcg.md`, generadas el 2026-10-29 en una máquina
Linux de 4 CPU con Python 3.12. Los tiempos dependen de la máquina; las tasas
de acierto no.

## 2. Nivel 1: el Mersenne Twister con salidas completas

### 2.1 Paso 1: invertir el tempering (`untemper`)

Cada salida del MT es `temper(palabra_del_estado)`. Si el tempering se puede
deshacer, cada salida revela una palabra del estado completa.

El tempering son cuatro pasos de dos tipos:

- `y ^= y >> s` (XOR con una copia desplazada a la derecha)
- `y ^= (y << s) & máscara` (XOR con una copia desplazada a la izquierda y
  filtrada)

Los dos se deshacen con la misma idea: **siempre hay un trozo de bits que no
ha cambiado**, y a partir de él se recupera el siguiente trozo.

- En `y ^= y >> 18`, los 18 bits altos del resultado son los originales,
  porque se hizo XOR con ceros. Como 18 ≥ 32 − 18, con esos bits ya se puede
  calcular `y >> 18` y deshacer el XOR del resto de una vez.
- En `y ^= (y << 7) & B`, los 7 bits bajos son los originales. Con ellos se
  recuperan los bits 7 a 13, con esos los bits 14 a 20, y así sucesivamente.
  Cada vuelta del bucle fija 7 bits más; en 5 vueltas están los 32.

`untemper` deshace los cuatro pasos en orden inverso:
`>> 18`, luego `<< 15 & C`, luego `<< 7 & B` y por último `>> 11`.

#### Ejemplo resuelto a mano: `untemper(0x00400091)`

En el documento 01 calculamos `temper(1) = 0x00400091`. Ahora vamos hacia
atrás.

**Paso A. Deshacer `y ^= y >> 18`.** Hay que aplicar la misma operación otra
vez, porque al ser 18 ≥ 16 es su propia inversa:
`0x00400091 >> 18 = 0x10`, así que `0x00400091 ⊕ 0x10 = 0x00400081`.

**Paso B. Deshacer `y ^= (y << 15) & 0xEFC60000`.** También basta con aplicarla
una vez. Al aplicarla dos veces aparece un término de segundo orden,
`(y << 30) & (C << 15) & C`, y ese término es cero: el bit activo más bajo de
C = `0xEFC60000` es el 17, y 17 + 15 = 32 cae fuera de la palabra, así que
`C << 15` vale 0 en 32 bits.
`0x00400081 << 15 = 0x00408000` (truncado a 32 bits); con la máscara queda
`0x00400000`; y `0x00400081 ⊕ 0x00400000 = 0x00000081`.

**Paso C. Deshacer `y ^= (y << 7) & 0x9D2C5680`, bit a bit.** Llamamos y a la
entrada, `0x81` (bits 7 y 0 a 1), y x al valor que buscamos. Se cumple
`x[i] = y[i] ⊕ (x[i−7] AND B[i])`.

| Bits | Cálculo | x |
|---|---|---|
| 0 a 6 | No cambiaron: x = y. | bit 0 = 1, resto 0 |
| 7 | y[7] = 1, x[0] = 1, B[7] = 1, así que 1 ⊕ (1·1) = 0 | 0 |
| 8 a 13 | y = 0 y x[1..6] = 0 | 0 |
| 14 a 31 | y = 0 y los x[i−7] son todos 0 | 0 |

Resultado: x = `0x00000001`.

**Paso D. Deshacer `y ^= y >> 11`.** `1 >> 11 = 0`, así que se queda en `0x00000001`.

**Resultado:** `untemper(0x00400091) = 1`. Lo comprueba el test
`test_untemper_worked_example`.

### 2.2 ¿Cómo sabemos que `untemper` es correcto para *todos* los valores?

Con dos argumentos independientes:

1. **Algebraico.** temper y untemper solo usan XOR, desplazamientos y AND con
   constantes, así que son **lineales sobre GF(2)**:
   f(a ⊕ b) = f(a) ⊕ f(b). Todo valor de 32 bits es el XOR de algunos de los
   32 vectores de la base eᵢ = 1 << i. Si `untemper(temper(eᵢ)) = eᵢ` para los
   32, entonces `untemper(temper(x)) = x` para todo x.

   Tests: `test_untemper_on_basis_vectors` y
   `test_temper_and_untemper_are_linear_over_gf2` (este último con hypothesis).
2. **Exhaustivo.** `test_untemper_exhaustive_all_2_32_values` recorre los
   4 294 967 296 valores posibles con la versión vectorizada en NumPy.

   Tarda unos 3,5 minutos (205 s medidos en la máquina de desarrollo), así que
   está marcado como `slow`: se ejecuta con `make test-slow` y en un trabajo
   propio de la CI.

### 2.3 Paso 2: reconstruir el estado con 624 salidas

Con `untemper` aplicado a 624 salidas consecutivas tenemos 624 palabras
consecutivas de la secuencia interna x₀, x₁, x₂… del generador. El twist es en
realidad una recurrencia:

```
x[k+624] = x[k+397] ⊕ A( bit alto de x[k] | 31 bits bajos de x[k+1] )
```

Cada palabra futura depende solo de palabras que están 624, 623 y 227
posiciones antes. Por tanto, **cualquier ventana de 624 palabras consecutivas
es un estado completo**.

#### La duda importante: ¿y si la observación no empieza al principio de un twist?

La víctima regenera su estado cada 624 salidas, pero el atacante empieza a
mirar en un momento cualquiera. Podría parecer que la ventana observada mezcla
palabras de dos generaciones del estado y no sirve. Sí sirve:

- El twist del código de referencia, aplicado sobre un vector con
  x[m], …, x[m+623], produce exactamente x[m+624], …, x[m+1247], **sea cual
  sea m**. Es la misma recurrencia escrita sobre un array circular.
- Por eso el clon se construye siempre como `MTState(palabras, pos=624)`: la
  próxima llamada hace un twist y saca x[m+624], que es justo la salida que
  viene después de la última observada.
- La posición interna del clon y la de la víctima no coinciden, pero la
  **secuencia de salidas** sí, y eso es lo único que importa.

El test `test_clone_predicts_next_10000_outputs_of_cpython` lo comprueba con
desplazamientos 0, 1, 300, 623, 624 y 1000. En el experimento E01, el
desplazamiento es aleatorio entre 0 y 2000 en cada ensayo.

### 2.4 Qué más se obtiene

Con el estado clonado se puede crear un `random.Random()` de Python
(`setstate`), que predice **cualquier** función del módulo: `random()`,
`randint(0, 36)` (una ruleta), `shuffle` (una baraja de 52 cartas) o `choice`.
Lo comprueba `test_cloned_state_drives_cpython_random_functions`. Este es el
puente con el casino simulado del H4.

Lo mismo funciona contra `numpy.random.RandomState` (`test_clone_numpy_randomstate`).

### 2.5 Control

Las 624 salidas de ChaCha20 o de `os.urandom` también se pueden "untemperar":
`untemper` es una biyección y acepta cualquier palabra. El estado resultante,
sin embargo, no tiene nada que ver con el generador real, y la tasa de acierto
es **0 %** en las 10 000 predicciones de cada ensayo de control. Por azar se
esperaría acertar 1 de cada 2³² palabras.

## 3. Nivel 5: el LCG de `java.util.Random`

### 3.1 La idea

El estado tiene 48 bits y `nextInt()` devuelve los 32 bits altos del estado
**recién calculado**. Tras ver la primera salida o₁ solo faltan 16 bits:

```
s₁ = o₁ · 2¹⁶ + b,   con b ∈ {0, …, 65 535} desconocido
```

Se prueban los 65 536 valores de b. Para cada uno se calcula
`s₂ = (s₁ · 0x5DEECE66D + 0xB) mod 2⁴⁸` y se comprueba si sus 32 bits altos
valen o₂. El que coincide es el estado real.

¿Puede coincidir uno falso? Para un b incorrecto, s₂ se comporta como un valor
cualquiera, y la probabilidad de que sus 32 bits altos coincidan por azar es
2⁻³². Con 2¹⁶ intentos, el número esperado de falsos positivos es
2¹⁶ · 2⁻³² = 2⁻¹⁶ ≈ 0,0015 %. Por eso la función devuelve una lista y, si se
pasa una tercera salida, la usa para descartar falsos. En el experimento E05,
los 100 ensayos dieron un candidato único con solo 2 salidas.

### 3.2 Ejemplo resuelto: `new Random(0)`

El JDK da como dos primeras salidas `nextInt()` = −1155484576 y −723955400.

1. Las pasamos a 32 bits sin signo: o₁ = `0xBB20B460` y o₂ = `0xD4D95138`.
2. Candidatos: s₁ = `0xBB20B460____`, donde los 4 dígitos finales son
   desconocidos.
3. El único que funciona es b = `0x0A74`: s₁ = `0xBB20B4600A74`, y su
   siguiente estado es s₂ = `0xBB20B4600A74 · 0x5DEECE66D + 0xB mod 2⁴⁸` =
   `0xD4D95138AB6F`, cuyos 32 bits altos son `0xD4D95138` = o₂ ✓.
4. Con s₂, el clon predice todas las salidas siguientes.

Es el mismo s₁ que calculamos hacia delante en el documento 01, sección 4.

### 3.3 Ir hacia atrás: recuperar la semilla

El multiplicador M = `0x5DEECE66D` es impar, así que tiene inverso módulo 2⁴⁸
(M⁻¹ = `0xDFE05BCB1365`, que Python calcula con `pow(M, -1, 2**48)`). Eso
permite deshacer pasos:

```
s_anterior = (s − 0xB) · M⁻¹ mod 2⁴⁸
```

En el ejemplo, retroceder un paso desde s₁ da `0x5DEECE66D`, que es el estado
inicial mezclado. Deshaciendo la mezcla (`⊕ 0x5DEECE66D`) sale la semilla 0.

Solo se recuperan los **48 bits bajos** de la semilla: `setSeed` descarta los
16 bits altos de un `long`. El test `test_recover_original_seed_low_48_bits`
lo comprueba con las semillas del JDK, incluidas −1 y `Long.MIN_VALUE`.

### 3.4 Variantes cubiertas

- **Un solo `nextLong()` basta**, porque son dos `next(32)` seguidos. Hay que
  deshacer un detalle: Java suma la mitad baja *con signo*, así que si es
  negativa le resta 1 a la mitad alta (`recover_state_from_long`).
- **Con el estado se predice cualquier método**, por ejemplo `nextInt(37)` para
  una ruleta: 100 % de acierto en 1 000 tiradas por ensayo.
- **Validación con datos del JDK real:** los tests atacan las salidas generadas
  por OpenJDK 21 (`tests/vectors/data/java_random.json`), no solo nuestra
  réplica.

### 3.5 Control

1 000 tríos de salidas de ChaCha20, tratados como si fueran de Java, dieron 0
estados compatibles, tanto con 2 salidas como con 3. Por azar se esperaban
≈ 0,015 en total con 2 salidas.

## 4. Coste en número de observaciones

| | MT19937 | `java.util.Random` |
|---|---|---|
| Bits de estado | 19 937 efectivos | 48 |
| Bits que revela cada salida | 32 | 32 |
| Mínimo teórico de salidas | ⌈19 937 / 32⌉ = 624 | ⌈48 / 32⌉ = 2 |
| Salidas que usa nuestro ataque | 624 | 2 (3 para garantizar unicidad) |

Los dos ataques están en el mínimo teórico. El MT necesita muchas más salidas
solo porque su estado es mucho mayor, no porque sea más seguro. En los dos
casos, la recuperación cuesta milisegundos.

---

## 5. Preguntas probables del tribunal

**Si el tempering se puede invertir, ¿para qué sirve?**
Para mejorar las propiedades estadísticas (la equidistribución en muchas
dimensiones), no para ocultar el estado. Matsumoto y Nishimura nunca
presentaron el MT como generador criptográfico.

**¿Por qué basta con comprobar 32 valores para demostrar que `untemper` funciona
para los 2³²?**
Porque las dos funciones son lineales sobre GF(2). Una aplicación lineal queda
determinada por lo que hace con los vectores de la base. Además, lo hemos
comprobado de forma exhaustiva con los 2³² valores, así que el resultado no
depende solo del argumento.

**¿Qué pasa si el atacante empieza a observar a mitad de un twist?**
Nada. Cualquier ventana de 624 salidas consecutivas determina todas las
siguientes, porque el twist es una recurrencia sobre la secuencia (sección
2.3). Está probado con desplazamientos 0, 1, 300, 623, 624, 1000 y aleatorios.

**¿Y si falta una sola salida, o el juego no muestra los 32 bits?**
Este ataque necesita las 624 salidas completas y consecutivas. Si faltan
salidas o solo se ven algunos bits, se pasa al ataque por sistemas de
ecuaciones sobre GF(2) (nivel 3, H5). Si el juego consume salidas que no
muestra, como en el muestreo con rechazo, es el nivel 7 (H10).

**¿Por qué fuerza bruta de 2¹⁶ en el LCG y no algo más elegante?**
Porque 65 536 pruebas tardan unos 20 ms en Python puro y el método se entiende
en una línea. Hay métodos algebraicos (por ejemplo, con retículos) que
recuperan LCG truncados con muchos más bits ocultos, pero aquí no hacen falta.

**¿Puede haber dos estados compatibles con las mismas dos salidas?**
Sí, con probabilidad ≈ 2⁻¹⁶. Por eso el ataque devuelve todos los candidatos y
una tercera salida deshace el empate. En 100 ensayos no hubo ninguno.

**¿Por qué el ataque "funciona" sobre ChaCha20 sin dar error?**
Porque `untemper` y la búsqueda del LCG aceptan cualquier entrada: no saben de
qué generador viene. Lo que demuestra el control es que el estado obtenido no
predice nada (0 % de acierto). Esa es la diferencia entre un generador
predecible y uno seguro.

**¿Esto significa que los casinos online son vulnerables?**
No. Significa que un sistema que use un PRNG no criptográfico y exponga sus
salidas es vulnerable. Las plataformas reguladas usan generadores
certificados. Este proyecto mide cuánto vale ese fallo, no dónde existe.
