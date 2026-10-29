# ADR 0002: uv como gestor de entorno y de dependencias

- **Estado:** Aceptado
- **Fecha:** 2026-10-29

## Contexto

La especificación pide `uv` o `pip-tools`, con versiones fijadas, para que
cualquiera pueda reproducir los resultados.

## Opciones consideradas

1. **pip-tools:** genera un `requirements.txt` con versiones fijadas a partir de
   un `requirements.in`. Es maduro, pero no gestiona la versión de Python y
   obliga a mantener un fichero por grupo de dependencias.
2. **uv:** un único `pyproject.toml` y un `uv.lock` multiplataforma con hashes.
   Instala también el intérprete (`.python-version` fija 3.12) y es mucho más
   rápido en la CI.

## Decisión

Se usa **uv**. El fichero `uv.lock` se versiona y la CI instala con
`uv sync --frozen`, que falla si el lock no coincide con `pyproject.toml`.

## Consecuencias

- Reproducibilidad: la misma versión de cada paquete en Linux, Windows y macOS.
- Quien no quiera usar uv puede exportar el lock:
  `uv export --format requirements-txt > requirements.txt`.
