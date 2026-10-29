// SPDX-License-Identifier: MIT
// Genera vectores de prueba de java.util.Random con el JDK instalado.
// Uso: java GenJavaVectors.java > java_random.json
//
// Los doubles se escriben como sus 64 bits (Double.doubleToRawLongBits) para
// comparar bit a bit, sin depender de cómo se imprime un decimal.

import java.util.Random;

public class GenJavaVectors {
    static final long[] SEEDS = {0L, 42L, -1L, 123456789L, (1L << 47) + 5L, Long.MIN_VALUE};
    static final int N_INT = 10000;
    static final int N_OTHER = 1000;
    static final int[] BOUNDS = {1, 2, 6, 37, 52, 1000, 1 << 20, (1 << 30) + 1, Integer.MAX_VALUE};

    public static void main(String[] args) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\n  \"generator\": \"java.util.Random\",\n");
        sb.append("  \"generated_with\": \"").append(System.getProperty("java.vendor"))
          .append(" ").append(System.getProperty("java.version")).append("\",\n");
        sb.append("  \"cases\": [\n");
        for (int s = 0; s < SEEDS.length; s++) {
            long seed = SEEDS[s];
            sb.append("    {\"seed\": ").append(seed);

            Random r = new Random(seed);
            sb.append(", \"next_int\": [");
            for (int i = 0; i < N_INT; i++) {
                if (i > 0) sb.append(',');
                sb.append(r.nextInt());
            }
            sb.append(']');

            sb.append(", \"next_int_bound\": {");
            for (int b = 0; b < BOUNDS.length; b++) {
                Random rb = new Random(seed);
                if (b > 0) sb.append(", ");
                sb.append('"').append(BOUNDS[b]).append("\": [");
                for (int i = 0; i < N_OTHER; i++) {
                    if (i > 0) sb.append(',');
                    sb.append(rb.nextInt(BOUNDS[b]));
                }
                sb.append(']');
            }
            sb.append('}');

            Random rl = new Random(seed);
            sb.append(", \"next_long\": [");
            for (int i = 0; i < N_OTHER; i++) {
                if (i > 0) sb.append(',');
                sb.append(rl.nextLong());
            }
            sb.append(']');

            Random rd = new Random(seed);
            sb.append(", \"next_double_bits\": [");
            for (int i = 0; i < N_OTHER; i++) {
                if (i > 0) sb.append(',');
                sb.append(Double.doubleToRawLongBits(rd.nextDouble()));
            }
            sb.append(']');

            Random rf = new Random(seed);
            sb.append(", \"next_float_bits\": [");
            for (int i = 0; i < N_OTHER; i++) {
                if (i > 0) sb.append(',');
                sb.append(Float.floatToRawIntBits(rf.nextFloat()));
            }
            sb.append(']');

            sb.append(s + 1 < SEEDS.length ? "},\n" : "}\n");
        }
        sb.append("  ]\n}\n");
        System.out.print(sb);
    }
}
