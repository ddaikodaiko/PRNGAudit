# ADR 0001: registrar las decisiones de arquitectura en ADR

- **Estado:** Aceptado
- **Fecha:** 2026-10-29

## Contexto

El proyecto se va a defender ante un tribunal y a someter a revisión técnica.
Hay que poder justificar cada elección, y sobre todo cada desviación respecto a
la especificación inicial.

## Decisión

Cada decisión que afecte a la arquitectura, a las dependencias, a la licencia o
al alcance se registra como un ADR numerado en `docs/adr/`, con la plantilla de
`0000-plantilla.md`. Si una elección de la especificación parece peor que una
alternativa, se propone un ADR **antes** de cambiarla y no se aplica hasta que
esté aceptado.

## Consecuencias

El historial de decisiones queda versionado junto al código. Un ADR aceptado no
se edita: si la decisión cambia, se escribe otro ADR que lo sustituye.
