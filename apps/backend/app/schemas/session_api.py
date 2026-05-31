"""Wrappers de respuesta de la API ``/v1/sessions`` (NO sagrados).

Estos schemas son los *envelopes* del wire HTTP de las read surfaces de
sesiones (``GET /v1/sessions``). **No** son tablas ni espejan el modelo: solo
paginan los ``SessionOut`` de ``app/schemas/session.py``, que se reusan tal cual
como ``items``.

Separación deliberada (igual que ``memory_api.py``): el ``*Out`` espejo del
modelo vive en ``app/schemas/session.py`` y el envelope de presentación
(``items`` + ``total``) vive acá, en un archivo de wrappers que no toca el
contrato de la sesión. ``schemas/session.py`` NO es sagrado (sagrado es solo
``schemas/{memory,audit}.py``), pero mantenemos la misma convención que la
memoria para que el patrón de paginación sea uniforme en toda la API.
"""

from __future__ import annotations

from app.schemas.base import YnaraBaseModel
from app.schemas.session import SessionOut


class SessionListPage(YnaraBaseModel):
    """Página de sesiones de chat: los ``items`` paginados + el ``total`` del user.

    ``items`` es la página ``limit``/``offset`` (ordenada por ``started_at DESC``);
    ``total`` es el conteo COMPLETO de sesiones del user (no el largo de la
    página), para que el cliente pueda paginar.
    """

    items: list[SessionOut]
    total: int
