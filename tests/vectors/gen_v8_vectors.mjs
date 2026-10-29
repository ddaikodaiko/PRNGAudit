// SPDX-License-Identifier: MIT
// Genera vectores de Math.random() del V8 de Node con semillas fijas.
// Uso: node gen_v8_vectors.mjs > v8_math_random.json
//
// Cada semilla se ejecuta en un proceso nuevo con `--random-seed`, porque el
// estado de Math.random() se siembra la primera vez que se usa en el proceso.
// Los doubles se guardan como sus 64 bits en hexadecimal.

import { execFileSync } from "node:child_process";

const SEEDS = [1, 42, 123456789, -7, 2147483647];
const N = 10000;

const child = `
const n = ${N};
const f = new Float64Array(1);
const u = new BigUint64Array(f.buffer);
const out = [];
for (let i = 0; i < n; i++) {
  f[0] = Math.random();
  out.push(u[0].toString(16).padStart(16, "0"));
}
process.stdout.write(JSON.stringify(out));
`;

const cases = SEEDS.map((seed) => {
  const raw = execFileSync(process.execPath, [`--random-seed=${seed}`, "-e", child], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  return { seed, math_random_bits: JSON.parse(raw) };
});

process.stdout.write(
  JSON.stringify(
    {
      generator: "V8 Math.random()",
      generated_with: `node ${process.version} (V8 ${process.versions.v8})`,
      cases,
    },
    null,
    1,
  ) + "\n",
);
