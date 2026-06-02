"""audit_log inmutable - trigger BEFORE UPDATE que bloquea cualquier UPDATE.

Enforcea a nivel de base de datos la invariante del modelo
``app/models/audit.py``: "una vez creada, una entrada de audit no se
modifica (solo ``created_at``)". El trigger dispara una EXCEPTION ante
cualquier UPDATE sobre ``audit_log``, dejando la inmutabilidad fuera del
alcance del ORM (la garantiza el motor aunque el SQL venga por fuera).

POR QUE SOLO UPDATE (y NO DELETE): la inmutabilidad se enforcea
exclusivamente contra UPDATE. DELETE queda permitido a proposito porque
lo necesitan dos caminos legitimos documentados en el modelo:

  (a) el ``ON DELETE CASCADE`` de ``users.id`` (derecho al olvido GDPR /
      regla #4 de AGENTS.md: los datos del usuario no quedan colgados), y
  (b) el worker periodico de retention de 24 meses (MEMORY.md).

Un trigger row-level BEFORE DELETE dispararia tambien dentro del cascade
y de la retention, rompiendo ambos. Por eso NO se bloquea DELETE.

Revision ID: a1f3c9d27e84
Revises: b7b06025f4bb
Create Date: 2026-06-02 10:15:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f3c9d27e84"
down_revision: str | None = "b7b06025f4bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Funcion trigger en PL/pgSQL: aborta cualquier UPDATE sobre audit_log.
    # ERRCODE 'check_violation' (23514) por ser un quiebre de invariante de
    # integridad de la tabla; el cliente puede discriminarlo del resto.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ynara_audit_log_block_update()
        RETURNS trigger AS $$
        BEGIN
            -- audit_log es append-only: la entrada no se modifica nunca.
            RAISE EXCEPTION
                'audit_log es inmutable: UPDATE no permitido '
                '(solo INSERT y DELETE por retention/cascade)'
                USING ERRCODE = 'check_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # Trigger row-level BEFORE UPDATE: SOLO UPDATE (DELETE queda permitido
    # a proposito para cascade GDPR + worker de retention). CREATE OR REPLACE
    # (PG14+) lo hace retry-safe, simetrico con el DROP IF EXISTS del downgrade.
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_audit_log_block_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION ynara_audit_log_block_update()
        """
    )


def downgrade() -> None:
    # Idempotente con IF EXISTS: primero el trigger, despues la funcion.
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_block_update ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS ynara_audit_log_block_update()")
