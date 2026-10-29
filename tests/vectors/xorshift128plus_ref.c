/* SPDX-License-Identifier: MIT */
/*
 * Referencia en C de xorshift128+ (Vigna, 2017; parámetros 23, 17, 26), con la
 * siembra MurmurHash3 de V8. Sirve para comprobar que la aritmética módulo 2^64
 * de la versión en Python (enteros sin límite + máscaras) coincide con la de C
 * (uint64_t, que desborda de forma natural).
 *
 * Transcrito de V8: src/base/utils/random-number-generator.h (XorShift128,
 * MurmurHash3) y src/numbers/math-random.cc (siembra de Math.random).
 *
 * Compilar y ejecutar: cc -O2 -std=c99 -o xs xorshift128plus_ref.c && ./xs > xorshift128plus.json
 */
#include <inttypes.h>
#include <stdio.h>

static uint64_t murmurhash3(uint64_t h) {
    h ^= h >> 33;
    h *= UINT64_C(0xFF51AFD7ED558CCD);
    h ^= h >> 33;
    h *= UINT64_C(0xC4CEB9FE1A85EC53);
    h ^= h >> 33;
    return h;
}

static uint64_t xorshift128(uint64_t *state0, uint64_t *state1) {
    uint64_t s1 = *state0;
    uint64_t s0 = *state1;
    *state0 = s0;
    s1 ^= s1 << 23;
    s1 ^= s1 >> 17;
    s1 ^= s0;
    s1 ^= s0 >> 26;
    *state1 = s1;
    return s0 + s1;
}

int main(void) {
    const int64_t seeds[] = {1, 42, 123456789, -7, INT64_MAX};
    const int nseeds = sizeof seeds / sizeof seeds[0];
    const int n = 10000;
    printf("{\n \"generator\": \"xorshift128+ (Vigna 23,17,26) con siembra de V8\",\n");
    printf(" \"generated_with\": \"referencia en C, uint64_t\",\n \"cases\": [\n");
    for (int k = 0; k < nseeds; k++) {
        uint64_t seed = (uint64_t)seeds[k];
        uint64_t s0 = murmurhash3(seed);
        uint64_t s1 = murmurhash3(~seed);
        printf("  {\"seed\": %" PRId64 ", \"next_u64\": [", seeds[k]);
        for (int i = 0; i < n; i++) {
            printf(i ? ",\"%016" PRIx64 "\"" : "\"%016" PRIx64 "\"", xorshift128(&s0, &s1));
        }
        printf(k + 1 < nseeds ? "]},\n" : "]}\n");
    }
    printf(" ]\n}\n");
    return 0;
}
