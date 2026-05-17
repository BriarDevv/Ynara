# SKILL: Crear un ADR

## Cuándo usar

Cuando una decisión técnica:
- Afecta la arquitectura (stack, modelos de datos, deploy).
- Es difícil de revertir.
- Genera consecuencias que merecen documentarse para futuros lectores.

Si la decisión es trivial o reversible en un commit, **no necesita
ADR**. Si dudás, ADR.

## Paso a paso

1. **Numerar**. El siguiente ADR libre. Mirar
   `docs/architecture/adrs/` y agarrar el próximo número.
2. **Archivo**. Crear
   `docs/architecture/adrs/ADR-XXX-titulo-en-kebab.md`.
3. **Plantilla** (copiar cualquiera de los ADRs existentes):
   ```md
   # ADR-XXX: Título

   ## Estado
   Propuesto | Aceptado | Superseded by ADR-YYY

   ## Fecha
   YYYY-MM-DD

   ## Contexto
   Qué problema estamos resolviendo.

   ## Decisión
   Qué decidimos hacer.

   ## Consecuencias positivas
   - …

   ## Consecuencias negativas
   - …

   ## Alternativas descartadas
   - …
   ```
4. **PR**. Discutir en el PR. Cambiar estado a "Aceptado" solo
   cuando se mergea.
5. **Inmutabilidad**. Una vez "Aceptado", **no se modifica más**. Si
   la decisión cambia, crear ADR nuevo que marca al anterior como
   "Superseded by ADR-YYY" en una sola edición chica.

## Checklist

- [ ] Número correcto (no duplicado, no salteado).
- [ ] Título descriptivo en kebab-case.
- [ ] Contexto explica el problema, no la solución.
- [ ] Alternativas descartadas con la razón.
- [ ] PR aprobado por al menos un CODEOWNER.
