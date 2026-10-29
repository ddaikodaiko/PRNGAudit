# ADR 0004: paquete Python en `src/prng_audit/`

- **Estado:** Aceptado
- **Fecha:** 2026-10-29

## Contexto

La especificación coloca `core/`, `sim/` y `api/` en la raíz del repositorio
como paquetes de primer nivel. Funciona, pero `core` y `api` son nombres muy
genéricos.

## Opciones consideradas

1. **Estructura literal** (`core/`, `sim/`, `api/` en la raíz). Riesgos:
   - choques de nombres con otros paquetes instalados (`import core` es ambiguo);
   - los tests pueden importar la carpeta suelta en lugar del paquete
     instalado y ocultar errores de empaquetado;
   - no se puede publicar en PyPI con esos nombres.
2. **Layout `src`:** un único paquete `prng_audit` con
   `src/prng_audit/{core,sim,api}`. `web/`, `experiments/`, `paper/`, `docs/` y
   `tests/` siguen en la raíz.

## Decisión

**Layout `src`.** Los módulos se importan como `prng_audit.core.generators`,
`prng_audit.sim`, etc. Los tests corren contra el paquete instalado
(`uv sync` lo instala en modo editable).

## Consecuencias

No cambia nada de lo que hace el proyecto, solo dónde vive cada carpeta. La
estructura de la especificación se mantiene dentro de `src/prng_audit/`.
