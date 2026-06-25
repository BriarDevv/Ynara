"""Tests de las superficies derivadas del dashboard **Hoy**: ``/v1/suggestions`` y
``/v1/recap`` (antes mock-only, ahora reales derivadas de las tareas del usuario).

Dos niveles (todos ``integration``, tocan la DB de tests vía ``db_session`` con el
patrón savepoint):

- **Servicio** (``build_suggestions`` / ``build_recap``) con ``now`` INYECTADO: asertan
  la lógica de derivación EXACTA de forma determinista (el "próximas" y el ``date``
  dependen de la hora, así que se fija ``now``).
- **HTTP** (``GET``): 200 + shape del wire, aislamiento por usuario, y 401 sin token.
  Usan horarios lejanos (2099/2000) para no depender de la hora real del runner.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import create_access_token
from app.enums import TaskStatus
from app.main import app
from app.models.task import Task
from app.models.user import User
from app.services.today import build_recap, build_suggestions

pytestmark = pytest.mark.integration

# ``now`` fijo para los tests de servicio: el mediodía del 2026-06-22 (UTC).
_NOW = datetime(2026, 6, 22, 12, 0, tzinfo=UTC)


async def _seed_user(session: AsyncSession) -> User:
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    title: str = "Tarea",
    status: TaskStatus = TaskStatus.PENDING,
    scheduled_at: str | None = None,
) -> Task:
    task = Task(
        user_id=user_id,
        title=title,
        status=status,
        scheduled_at=datetime.fromisoformat(scheduled_at) if scheduled_at else None,
    )
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Suggestions (servicio, now inyectado)
# ---------------------------------------------------------------------------


async def test_suggestions_surface_upcoming_pending_only(db_session: AsyncSession) -> None:
    """Solo las pendientes con horario A FUTURO (respecto de ``now``) son nudges."""
    user = await _seed_user(db_session)
    # futura pendiente -> SÍ.
    await _seed_task(
        db_session, user_id=user.id, title="Reunión", scheduled_at="2026-06-22T18:00:00+00:00"
    )
    # pasada pendiente -> NO (ya pasó).
    await _seed_task(
        db_session, user_id=user.id, title="Vieja", scheduled_at="2026-06-22T06:00:00+00:00"
    )
    # futura pero DONE -> NO (no es un pendiente por preparar).
    await _seed_task(
        db_session,
        user_id=user.id,
        title="Hecha",
        status=TaskStatus.DONE,
        scheduled_at="2026-06-22T20:00:00+00:00",
    )
    # pendiente SIN horario -> NO (no se puede "preparar para" sin cuándo).
    await _seed_task(db_session, user_id=user.id, title="Sin hora")

    out = await build_suggestions(db_session, user.id, now=_NOW)

    assert len(out) == 1
    assert out[0].title == "Preparate para Reunión"
    assert out[0].mode is None  # v1 transversal: no derivamos el modo real (≠ un fijo incorrecto)
    assert out[0].why  # tiene un porqué no vacío


async def test_suggestions_cap_and_order(db_session: AsyncSession) -> None:
    """Surfacea hasta 2 nudges, las próximas primero (orden por horario asc)."""
    user = await _seed_user(db_session)
    for hour, title in ((20, "Tres"), (16, "Dos"), (14, "Una")):
        await _seed_task(
            db_session, user_id=user.id, title=title, scheduled_at=f"2026-06-22T{hour}:00:00+00:00"
        )

    out = await build_suggestions(db_session, user.id, now=_NOW)

    assert [s.title for s in out] == ["Preparate para Una", "Preparate para Dos"]  # cap 2, asc


async def test_suggestions_empty_when_nothing_upcoming(db_session: AsyncSession) -> None:
    """Sin pendientes a futuro → lista vacía (la web oculta la sección)."""
    user = await _seed_user(db_session)
    await _seed_task(
        db_session, user_id=user.id, title="Pasada", scheduled_at="2026-06-22T06:00:00+00:00"
    )

    assert await build_suggestions(db_session, user.id, now=_NOW) == []


async def test_suggestions_id_is_stable_per_task(db_session: AsyncSession) -> None:
    """El id de la sugerencia es estable entre requests (misma tarea → mismo id)."""
    user = await _seed_user(db_session)
    await _seed_task(
        db_session, user_id=user.id, title="X", scheduled_at="2026-06-22T18:00:00+00:00"
    )

    first = await build_suggestions(db_session, user.id, now=_NOW)
    second = await build_suggestions(db_session, user.id, now=_NOW)

    assert first[0].id == second[0].id


async def test_suggestions_isolation(db_session: AsyncSession) -> None:
    """Las sugerencias de A no incluyen tareas de B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    await _seed_task(
        db_session, user_id=user_b.id, title="De B", scheduled_at="2026-06-22T18:00:00+00:00"
    )

    assert await build_suggestions(db_session, user_a.id, now=_NOW) == []


# ---------------------------------------------------------------------------
# Recap (servicio, now inyectado)
# ---------------------------------------------------------------------------


async def test_recap_pending_with_real_highlights(db_session: AsyncSession) -> None:
    """Con tareas reales → pending=True, highlights de las cerradas + el pendiente."""
    user = await _seed_user(db_session)
    await _seed_task(db_session, user_id=user.id, title="Mail", status=TaskStatus.DONE)
    await _seed_task(db_session, user_id=user.id, title="Llamada", status=TaskStatus.PENDING)

    recap = await build_recap(db_session, user.id, now=_NOW)

    assert recap.pending is True
    assert recap.date == _NOW
    assert "Cerraste: Mail" in recap.highlights
    assert any("1 prioridad" in h for h in recap.highlights)
    assert recap.headline  # frase derivada presente


async def test_recap_empty_when_no_tasks(db_session: AsyncSession) -> None:
    """Sin tareas → pending=False, headline=None, highlights=[] (oculta el CTA)."""
    user = await _seed_user(db_session)

    recap = await build_recap(db_session, user.id, now=_NOW)

    assert recap.pending is False
    assert recap.headline is None
    assert recap.highlights == []


async def test_recap_all_done_headline(db_session: AsyncSession) -> None:
    """Todo hecho y nada pendiente → headline de cierre completo."""
    user = await _seed_user(db_session)
    await _seed_task(db_session, user_id=user.id, title="A", status=TaskStatus.DONE)

    recap = await build_recap(db_session, user.id, now=_NOW)

    assert recap.pending is True
    assert recap.headline == "Cerraste todo lo del día. Bien ahí."


async def test_recap_dedups_identical_done_titles(db_session: AsyncSession) -> None:
    """Dos tareas cerradas con el MISMO título → una sola línea (highlights únicos)."""
    user = await _seed_user(db_session)
    await _seed_task(db_session, user_id=user.id, title="Reunión", status=TaskStatus.DONE)
    await _seed_task(db_session, user_id=user.id, title="Reunión", status=TaskStatus.DONE)

    recap = await build_recap(db_session, user.id, now=_NOW)

    assert recap.highlights.count("Cerraste: Reunión") == 1


async def test_recap_isolation(db_session: AsyncSession) -> None:
    """El recap de A no se arma con tareas de B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    await _seed_task(db_session, user_id=user_b.id, title="De B", status=TaskStatus.DONE)

    recap = await build_recap(db_session, user_a.id, now=_NOW)

    assert recap.pending is False
    assert recap.highlights == []


# ---------------------------------------------------------------------------
# HTTP (200 / shape / 401)
# ---------------------------------------------------------------------------


async def test_get_suggestions_http_shape(db_session: AsyncSession) -> None:
    """GET /v1/suggestions → 200 con ``items`` y cada item con las 4 keys del wire."""
    user = await _seed_user(db_session)
    await _seed_task(
        db_session, user_id=user.id, title="Demo", scheduled_at="2099-01-01T10:00:00+00:00"
    )

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/suggestions", headers=_bearer(user.id))

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items"}
        assert len(body["items"]) == 1
        assert set(body["items"][0].keys()) == {"id", "title", "why", "mode"}
        assert body["items"][0]["mode"] is None  # transversal en v1
    finally:
        app.dependency_overrides.clear()


async def test_get_recap_http_shape(db_session: AsyncSession) -> None:
    """GET /v1/recap → 200 con las 4 keys del wire y pending=True con contenido."""
    user = await _seed_user(db_session)
    await _seed_task(db_session, user_id=user.id, title="Hecha", status=TaskStatus.DONE)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/recap", headers=_bearer(user.id))

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"pending", "date", "headline", "highlights"}
        assert body["pending"] is True
        assert "Cerraste: Hecha" in body["highlights"]
    finally:
        app.dependency_overrides.clear()


async def test_today_without_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 en ambas rutas."""
    client = await _client(db_session)
    try:
        async with client:
            r_sug = await client.get("/v1/suggestions")
            r_rec = await client.get("/v1/recap")
        assert r_sug.status_code == 401
        assert r_rec.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_today_rate_limited_429(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cruzar el rate-limit (bucket del dashboard Hoy) → 429 + ``Retry-After`` en ambas."""
    user = await _seed_user(db_session)

    async def _deny(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr("app.api.v1.today.check_tasks_rate_limit", _deny)

    client = await _client(db_session)
    try:
        async with client:
            r_sug = await client.get("/v1/suggestions", headers=_bearer(user.id))
            r_rec = await client.get("/v1/recap", headers=_bearer(user.id))
        assert r_sug.status_code == 429
        assert "Retry-After" in r_sug.headers
        assert r_rec.status_code == 429
        assert "Retry-After" in r_rec.headers
    finally:
        app.dependency_overrides.clear()
