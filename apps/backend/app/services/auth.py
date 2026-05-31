"""Service de autenticación: registro + verificación de credenciales.

Capa de dominio entre los endpoints (``app/api/v1/auth.py``) y la persistencia.
Encapsula el hashing (delegado en ``app/core/security.py``), la normalización de
email y las dos garantías de seguridad del módulo:

(1) Anti-enumeración en login. ``authenticate_user`` devuelve ``None`` sin
    distinguir "el email no existe" de "el password está mal": el endpoint
    traduce ambos al MISMO 401. NUNCA un 404.

(2) Timing-safe en login. Cuando el usuario no existe (o existe pero su
    ``password_hash`` es ``None`` — usuario efímero), igual se corre
    ``verify_password`` contra un hash dummy precomputado y se descarta el
    resultado. Sin esto, el camino "email inexistente" volvería notablemente más
    rápido (no hace bcrypt) y filtraría qué emails están registrados por timing.

Regla #4: ningún password ni hash se loguea, se devuelve ni se mete en una
excepción. Las excepciones de dominio (``EmailAlreadyRegisteredError``) son
señales sin payload sensible.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User

# Hash dummy precomputado UNA vez a import-time (no por request): el password en
# claro es irrelevante, solo importa tener un hash bcrypt válido contra el que
# correr ``verify_password`` cuando el usuario no existe (timing-safe). El valor
# es de relleno, no una credencial real.
_DUMMY_HASH = hash_password("ynara-timing-safe-dummy")


class EmailAlreadyRegisteredError(Exception):
    """El email ya está registrado (señal de dominio para el 409 del endpoint).

    Se levanta tras un ``IntegrityError`` de ``uq_users_email`` (incluida la
    carrera de dos register simultáneos). El service hace ``rollback`` antes de
    levantarla: la sesión queda limpia para que el endpoint pueda responder.
    """


def _normalize_email(email: str) -> str:
    """Normaliza un email para comparación/almacenamiento: trim + lower.

    IDÉNTICA en register y login: si difirieran, un usuario registrado como
    ``A@X.com`` no podría loguearse con ``a@x.com`` (o peor, se permitiría un
    duplicado que la unique constraint sí colapsaría, dando un 500 en vez del
    409 esperado).
    """
    return email.strip().lower()


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str | None,
) -> User:
    """Crea un usuario con email + password hasheado. NO commitea (lo hace el endpoint).

    Patrón transaccional espejado de ``chat.py``: ``add`` -> ``flush`` (asigna el
    ``id`` y dispara la unique constraint) -> ``refresh`` (puebla los
    server-defaults: ``id`` / ``created_at`` / ``updated_at``). El commit es
    responsabilidad del endpoint.

    Ante un ``IntegrityError`` (violación de ``uq_users_email``, incluida la
    carrera de dos register simultáneos sobre el mismo email) hace ``rollback``
    de la sesión y levanta ``EmailAlreadyRegisteredError``. El ``rollback`` es
    crítico: ``get_db`` NO rollbackea ante una ``HTTPException``, así que sin él
    la sesión quedaría en estado ``PendingRollback`` y el commit del endpoint
    explotaría.

    Args:
        session: sesión async; se le hace flush/refresh pero NO commit.
        email: email en crudo del wire; se normaliza acá.
        password: password en claro; se hashea acá (nunca se persiste el claro).
        display_name: nombre opcional (ya validado por el schema, <=40 chars).

    Returns:
        El ``User`` recién creado, con ``id`` y timestamps poblados.

    Raises:
        EmailAlreadyRegisteredError: si el email ya estaba registrado.
    """
    user = User(
        email=_normalize_email(email),
        password_hash=hash_password(password),
        display_name=display_name,
        is_ephemeral=False,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Email duplicado (uq_users_email) o carrera de dos register. Rollback
        # ANTES de señalizar: deja la sesión usable para el endpoint (get_db no
        # rollbackea ante HTTPException).
        await session.rollback()
        raise EmailAlreadyRegisteredError from exc
    # Poblar server-defaults (id / created_at / updated_at) sin commitear.
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User | None:
    """Verifica credenciales. Devuelve el ``User`` si son válidas, si no ``None``.

    Read-only: NO commitea. La normalización del email es IDÉNTICA a la de
    ``register_user``.

    Anti-enumeración + timing-safe: cuando el usuario no existe O existe pero su
    ``password_hash`` es ``None`` (usuario efímero), se corre igual
    ``verify_password`` contra ``_DUMMY_HASH`` y se descarta el resultado, para
    que el costo en tiempo sea equivalente al del camino con password válido. En
    todos los casos de fallo se devuelve ``None`` sin distinguir el motivo; el
    endpoint traduce ese ``None`` a un 401 uniforme.

    Returns:
        El ``User`` si email + password coinciden; ``None`` en cualquier fallo
        (email inexistente, sin hash, o password incorrecto).
    """
    normalized = _normalize_email(email)
    user = await session.scalar(select(User).where(User.email == normalized))

    if user is None or user.password_hash is None:
        # Correr y DESCARTAR: equipara el tiempo con el camino "usuario válido"
        # (bcrypt domina el costo); sin esto, el email inexistente respondería
        # más rápido y filtraría qué emails están registrados.
        verify_password(password, _DUMMY_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user
