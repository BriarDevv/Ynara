"""Tests del service ``register_user`` en el camino del ``except IntegrityError``.

Foco: el bloque ``except IntegrityError`` REAL de ``app/services/auth.py``
(``register_user``, aprox. líneas 100-108). Cuando dos registros del mismo email
compiten, la unique constraint ``uq_users_email`` dispara un ``IntegrityError`` en
el ``flush``; el service lo captura, hace ``rollback`` de la sesión y re-señaliza
como ``EmailAlreadyRegisteredError`` SIN revelar que el email ya existe
(anti-enumeración, regla #4: la excepción de dominio no lleva payload sensible).

A diferencia de ``tests/api/test_auth.py`` (E2E sobre el endpoint), acá se llama al
service DIRECTO con el ``db_session`` del fixture: el ``IntegrityError`` se fuerza
de verdad contra el constraint de Postgres (NO mockeado), ejercitando el camino del
``except`` línea por línea.

Todos son ``integration`` (tocan la DB de tests dedicada vía ``db_session``, con
aislamiento por savepoint: ver ``tests/conftest.py``).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.auth import (
    EmailAlreadyRegisteredError,
    _normalize_email,
    register_user,
)

pytestmark = pytest.mark.integration


async def test_register_user_duplicado_dispara_except_integrityerror(
    db_session: AsyncSession,
) -> None:
    """Un email ya sembrado -> ``register_user`` cae en el ``except`` y re-señaliza.

    Siembra un ``User`` con un email y lo flushea (la fila ya vive bajo el constraint
    ``uq_users_email``). Después invoca ``register_user`` con el MISMO email: el
    ``flush`` interno viola la unique constraint, el ``IntegrityError`` se dispara de
    verdad (no mockeado) y el service lo traduce a ``EmailAlreadyRegisteredError``.
    """
    email = "race.dup@example.com"
    seeded = User(
        email=_normalize_email(email),
        password_hash="hash-de-relleno-no-credencial",
        is_ephemeral=False,
    )
    db_session.add(seeded)
    await db_session.flush()

    # El segundo register sobre el mismo email DEBE caer en el except IntegrityError.
    with pytest.raises(EmailAlreadyRegisteredError):
        await register_user(
            db_session,
            email=email,
            password="otrapass12345",
            display_name="Segundo",
        )


async def test_register_user_integrityerror_no_revela_existencia(
    db_session: AsyncSession,
) -> None:
    """La ``EmailAlreadyRegisteredError`` no filtra el email ni un oráculo de existencia.

    Anti-enumeración (regla #4): la señal de dominio NO debe llevar el email, ni el
    hash, ni un texto del tipo "ya existe"/"exists" que delate qué emails están
    registrados. El except sólo re-levanta una señal vacía encadenada al original.
    """
    email = "race.silent@example.com"
    seeded = User(
        email=_normalize_email(email),
        password_hash="hash-de-relleno-no-credencial",
        is_ephemeral=False,
    )
    db_session.add(seeded)
    await db_session.flush()

    with pytest.raises(EmailAlreadyRegisteredError) as excinfo:
        await register_user(
            db_session,
            email=email,
            password="supersecreta1",
            display_name=None,
        )

    rendered = str(excinfo.value).lower()
    # Sin oráculo de enumeración: ni el email crudo ni vocabulario de "existe".
    assert email.lower() not in rendered
    assert "exist" not in rendered
    assert "registrad" not in rendered
    assert "duplicad" not in rendered
    # Regla #4: ni el password ni el hash de relleno se filtran en la excepción.
    assert "supersecreta1" not in rendered
    assert "hash-de-relleno-no-credencial" not in rendered


async def test_register_user_integrityerror_deja_sesion_usable(
    db_session: AsyncSession,
) -> None:
    """Tras el except, el ``rollback`` del service deja la sesión sin ``PendingRollback``.

    El ``rollback`` interno es crítico: ``get_db`` no rollbackea ante una
    ``HTTPException``, así que sin él la sesión quedaría en ``PendingRollback`` y el
    commit del endpoint explotaría. Verificamos que, tras el except, una query nueva
    corre sobre la MISMA sesión sin tronar (si quedara ``PendingRollback``, el
    ``scalar`` siguiente levantaría ``PendingRollbackError`` en vez de devolver un
    entero).

    No se asserta el conteo de filas: bajo el aislamiento por savepoint del fixture,
    el ``rollback`` del service rebobina al savepoint que envuelve este test (incluida
    la fila sembrada). Lo que importa acá es que la sesión sobreviva al except y
    siga siendo consultable.
    """
    email = "race.usable@example.com"
    seeded = User(
        email=_normalize_email(email),
        password_hash="hash-de-relleno-no-credencial",
        is_ephemeral=False,
    )
    db_session.add(seeded)
    await db_session.flush()

    with pytest.raises(EmailAlreadyRegisteredError):
        await register_user(
            db_session,
            email=email,
            password="otrapass12345",
            display_name=None,
        )

    # La sesión sigue operativa: una query post-except devuelve un int en vez de
    # levantar PendingRollbackError. El register fallido tampoco dejó una fila
    # duplicada: el conteo nunca es 2.
    count = await db_session.scalar(
        select(func.count()).select_from(User).where(User.email == _normalize_email(email))
    )
    assert isinstance(count, int)
    assert count < 2


async def test_register_user_carrera_real_dos_registros(
    db_session: AsyncSession,
) -> None:
    """Dos ``register_user`` consecutivos del mismo email: el segundo cae en el except.

    Modela la carrera del contrato del service: el PRIMER register crea la fila vía
    el camino feliz (``flush`` + ``refresh``), el SEGUNDO sobre el mismo email choca
    contra ``uq_users_email`` y dispara el ``IntegrityError`` real -> el except lo
    re-señaliza. El ``IntegrityError`` lo produce un register previo de verdad, no un
    seed manual.
    """
    email = "race.twice@example.com"

    first = await register_user(
        db_session,
        email=email,
        password="supersecreta1",
        display_name="Primero",
    )
    # El camino feliz pobló el id y el email normalizado.
    assert first.id is not None
    assert first.email == _normalize_email(email)

    with pytest.raises(EmailAlreadyRegisteredError):
        await register_user(
            db_session,
            email=email,
            password="otrapass12345",
            display_name="Segundo",
        )
