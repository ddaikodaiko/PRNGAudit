# ADR 0003: licencia MIT

- **Estado:** Aceptado
- **Fecha:** 2026-10-29

## Contexto

El proyecto va a un portfolio público, a una publicación técnica (JOSS como
destino posible) y a una release con DOI en Zenodo. Necesita una licencia de
código abierto aprobada por la OSI y decidida desde el principio, para no tener
que cambiar las cabeceras de los ficheros más adelante.

## Opciones consideradas

1. **MIT:** permisiva, muy corta, la más común en JOSS y en portfolios. Se
   entiende en una línea: haz lo que quieras, pero conserva el aviso de
   copyright.
2. **Apache-2.0:** también permisiva, añade una concesión explícita de patentes
   y reglas sobre contribuciones. Esa concesión importa cuando contribuyen
   empresas con patentes, que no es el caso de este proyecto.

## Decisión

**MIT.** Cada fichero fuente lleva la cabecera
`SPDX-License-Identifier: MIT`, y la licencia completa está en `LICENSE`.

## Consecuencias

Cualquiera puede reutilizar el código, también con fines comerciales,
manteniendo el aviso de copyright. Si en el futuro contribuye una empresa, se
puede reconsiderar con un ADR nuevo.
