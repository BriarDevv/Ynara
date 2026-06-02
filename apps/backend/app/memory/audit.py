"""Sede de escritura de la tabla sagrada ``audit_log`` (issue #158).

``AuditStore`` es el ÚNICO punto de ``app/`` que INSERTA filas en
``audit_log``. El modelo (``app/models/audit.py``) y la migración ya existían
desde PR #15; lo que faltaba era construir la escritura. Acá se cierra ese gap:
cada op de memoria APLICADA en la consolidación (``apply_ops``) deja una fila
de auditoría.

REGLA #4 (perímetro de privacidad — NO negociable): la fila de ``audit_log``
NUNCA guarda contenido del usuario en claro. Solo viaja METADATA de la
operación (``operation`` / ``target_layer`` / ``target_id`` / ``origin_*`` /
``sensitive``) más un ``record_hash``: un sha256 hex (64 chars) del
contenido/identificador afectado, NO el contenido. El ``record_hash`` es
unidireccional (no se puede revertir al texto), así que cero PII llega a la
tabla de auditoría. El que computa el hash es el caller (``apply_ops``); este
store solo persiste el digest ya calculado.

Patrón (igual que ``SemanticMemoryStore`` / ``ProceduralMemoryStore``): store
por-request, con ``session`` + ``user_id`` ligados en el ``__init__`` (el
``user_id`` nunca viaja como argumento de método, así toda fila queda
forzosamente atada al usuario del store — aislamiento estructural, regla #3).
Hace ``flush()``, NO ``commit()``: el commit lo da el caller (el worker de
consolidación o el fixture del test) en la misma transacción que las ops de
memoria, así la auditoría es atómica con la escritura que audita.
"""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AuditOperation, LlmModel, MemoryLayer, Mode
from app.models.audit import AuditLog

# Forma del record_hash (idéntica al CHECK ``record_hash_sha256_hex`` del modelo).
# Se valida acá ANTES del insert para que un caller que mande algo mal formado
# —o, peor, plaintext— falle claro y temprano en vez de recibir un IntegrityError
# opaco de Postgres en el flush. El store es el guardián de su invariante.
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class AuditStore:
    """Store por-request de ``audit_log``, ligado a un ``user_id``.

    El ``user_id`` se liga en el constructor: cada fila de auditoría queda
    atada al usuario del store sin que el caller pueda variarlo (aislamiento
    estructural, igual que los stores de memoria).
    """

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id

    async def record(
        self,
        *,
        operation: AuditOperation,
        target_layer: MemoryLayer,
        target_id: UUID | None,
        record_hash: str,
        origin_model: LlmModel | None = None,
        origin_mode: Mode | None = None,
        origin_tool: str | None = None,
        sensitive: bool = False,
    ) -> None:
        """Inserta una fila de auditoría para la op recibida.

        REGLA #4: ``record_hash`` es el sha256 hex (64 chars) del contenido o
        identificador afectado, calculado por el caller — NUNCA el contenido en
        claro. Ningún argumento de este método transporta PII: ``target_id`` es
        un UUID, ``origin_*`` son enums/nombres de tool, ``record_hash`` es un
        digest unidireccional. Nada de texto de usuario llega a ``audit_log``.

        Hace ``flush()`` (no ``commit()``): el commit lo da el caller en la
        misma transacción que la op de memoria que se está auditando.
        """
        if not _SHA256_HEX.match(record_hash):
            # NO se loguea el valor (regla #4: podría ser plaintext mal pasado).
            raise ValueError("record_hash debe ser un sha256 hex de 64 caracteres")
        row = AuditLog(
            user_id=self._user_id,
            operation=operation,
            target_layer=target_layer,
            target_id=target_id,
            record_hash=record_hash,
            origin_model=origin_model,
            origin_mode=origin_mode,
            origin_tool=origin_tool,
            sensitive=sensitive,
        )
        self._session.add(row)
        await self._session.flush()
