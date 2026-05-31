"""Tests E2E de ``/v1/memory`` (Ola 1 read-only + Ola 2 PATCH/DELETE — TABLA SAGRADA).

Todos son ``integration`` (tocan el pgvector REAL vía ``db_session``). Los GET de Ola 1
son read-only; los PATCH/DELETE de Ola 2 SÍ commitean (como en prod). El fixture
``db_session`` aísla cada test con un savepoint sobre una transacción externa que se
revierte al final, así que esos commits NO filtran filas entre tests y no hace falta
limpieza manual (ver ``tests/conftest.py``).

Patrón (igual que ``test_chat.py`` / ``test_sessions_close.py``):

- ``httpx.AsyncClient`` + ``ASGITransport(app=app)`` golpea la app real.
- ``app.dependency_overrides[get_db]`` cede el ``db_session`` del fixture, así el
  endpoint lee la MISMA sesión donde el test sembró (con ``flush``, sin commit).
- Se overridea ``get_embedder`` / ``get_reranker`` con los Fake (el ``list_all`` /
  ``get_by_id`` NO embeddean, pero el ``__init__`` de los stores sagrados los pide;
  el lifespan no corre bajo ``ASGITransport`` sin startup, así que se inyectan a mano).

La memoria se siembra con los **stores reales** (cifrado AES-256-GCM correcto vía
``crypto.py``), nunca con INSERTs crudos de plaintext: así el round-trip de
descifrado se ejercita de punta a punta.

Cubre el spec (aislamiento es el test CLAVE):
1. ``GET /memory`` sin layer → agrupado, solo la memoria del user, totales correctos.
2. ``GET /memory?layer=semantic`` → solo semantic, paginado (limit/offset).
3. ``GET /memory/semantic/{id}`` propio → 200 con content descifrado + metadata.
4. AISLAMIENTO: ``GET /memory/semantic/{id}`` de OTRO user → 404 (no leak). Idem procedural.
5. ``GET /memory/semantic/{uuid-inexistente}`` → 404 (mismo detail que ajena).
6. ``GET /memory/export`` → 3 capas solo del user, descifradas, version + Content-Disposition.
7. limit fuera de rango (0 / 101) → 422; ref no-UUID en semantic → 422.
8. sin token → 401.
9. (seguridad) ninguna respuesta trae el blob cifrado crudo / bytes.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_embedder, get_reranker
from app.core.security import create_access_token
from app.enums import Mode
from app.llm.clients.embedding import FakeEmbeddingClient
from app.llm.clients.reranker import FakeReranker
from app.main import app
from app.memory.episodic import EpisodicMemoryStore
from app.memory.procedural import ProceduralMemoryStore
from app.memory.semantic import SemanticMemoryStore
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.memory import (
    EpisodicMemoryCreate,
    ProceduralMemoryUpsert,
    SemanticMemoryCreate,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers de siembra (flush, NO commit — el rollback del fixture limpia)
# ---------------------------------------------------------------------------


async def _seed_user(session: AsyncSession) -> User:
    """Inserta un User mínimo y hace flush para que tenga id asignado."""
    user = User()
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _seed_chat_session(session: AsyncSession, user_id: uuid.UUID) -> ChatSession:
    """Inserta una ChatSession (FK que la episódica necesita en session_id)."""
    cs = ChatSession(user_id=user_id, mode=Mode.PRODUCTIVIDAD)
    session.add(cs)
    await session.flush()
    await session.refresh(cs)
    return cs


def _stores(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[SemanticMemoryStore, EpisodicMemoryStore, ProceduralMemoryStore]:
    embedder = FakeEmbeddingClient()
    reranker = FakeReranker()
    return (
        SemanticMemoryStore(session, user_id, embedder, reranker),
        EpisodicMemoryStore(session, user_id, embedder, reranker),
        ProceduralMemoryStore(session, user_id),
    )


async def _seed_full_memory(
    session: AsyncSession, user: User, *, tag: str
) -> dict[str, uuid.UUID | str]:
    """Siembra 1 hecho semántico, 1 episodio y 1 preferencia procedural para el user.

    Devuelve las refs (ids / key) para que el test las consulte por el endpoint.
    El ``tag`` distingue el contenido entre users (para el assert de aislamiento).
    """
    cs = await _seed_chat_session(session, user.id)
    semantic, episodic, procedural = _stores(session, user.id)

    sem = await semantic.add(SemanticMemoryCreate(content=f"hecho semantico de {tag}"))
    epi = await episodic.add(
        EpisodicMemoryCreate(
            session_id=cs.id,
            summary=f"resumen episodico de {tag}",
            occurred_at=cs.started_at,
            is_sensitive=False,
            retention_days=90,
            topics={"tag": tag},
        )
    )
    proc = await procedural.upsert(ProceduralMemoryUpsert(key=f"pref.{tag}", value={"tag": tag}))
    await session.flush()
    return {"semantic_id": sem.id, "episodic_id": epi.id, "procedural_key": proc.key}


def _bearer(user_id: uuid.UUID) -> dict[str, str]:
    """Header Authorization con un JWT válido para ``user_id``."""
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


async def _client(db_session: AsyncSession) -> httpx.AsyncClient:
    """Overridea ``get_db`` + clientes Fake y devuelve el cliente ASGI.

    El caller usa el cliente dentro de ``async with`` y limpia los overrides en su
    ``finally`` con ``app.dependency_overrides.clear()``. Los Fake se overridean
    porque el lifespan (que los pone en ``app.state``) no corre bajo
    ``ASGITransport`` sin gestionar el startup.
    """

    async def _override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_embedder] = lambda: FakeEmbeddingClient()
    app.dependency_overrides[get_reranker] = lambda: FakeReranker()
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _assert_no_raw_blob(payload: object) -> None:
    """Assert recursivo: ningún string de la respuesta es base64/hex del BYTEA crudo.

    Defensa del invariante #9: el blob cifrado NUNCA viaja. Como la respuesta es JSON
    (sin ``bytes`` nativo posible), se chequea que ningún campo string contenga el
    marcador de bytes de Python (``\\x``) ni la pinta de un blob no-UTF8; en la
    práctica el content/summary van en plaintext legible y los ids son UUID. Se
    asegura además que no aparezca ninguna key sospechosa de blob crudo.
    """
    forbidden_keys = {"content_embedding", "summary_embedding"}
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert key not in forbidden_keys, f"la respuesta no debe exponer {key}"
            _assert_no_raw_blob(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_raw_blob(item)
    elif isinstance(payload, str):
        # Un blob cifrado decodificado a str tendría bytes de control; el plaintext no.
        assert "\\x" not in payload, "la respuesta no debe contener el repr de bytes crudos"


# ---------------------------------------------------------------------------
# 1. GET /memory (sin layer) → agrupado, solo la memoria del user, totales OK
# ---------------------------------------------------------------------------


async def test_list_memory_grouped_only_own(db_session: AsyncSession) -> None:
    """Agrupado por capa; cada capa trae 1 item del user A, totales == 1, nada de B."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    refs_a = await _seed_full_memory(db_session, user_a, tag="A")
    await _seed_full_memory(db_session, user_b, tag="B")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/memory", headers=_bearer(user_a.id))

        assert resp.status_code == 200
        body = resp.json()

        # Las 3 capas presentes, cada una con su total del user A.
        assert set(body.keys()) == {"semantic", "episodic", "procedural"}
        assert body["semantic"]["total"] == 1
        assert body["episodic"]["total"] == 1
        assert body["procedural"]["total"] == 1

        # El único item semantic es el de A (content descifrado, tag A), no el de B.
        sem_items = body["semantic"]["items"]
        assert len(sem_items) == 1
        assert sem_items[0]["id"] == str(refs_a["semantic_id"])
        assert sem_items[0]["content"] == "hecho semantico de A"
        assert all(it["user_id"] == str(user_a.id) for it in sem_items)

        # Episódico y procedural también solo de A.
        assert body["episodic"]["items"][0]["summary"] == "resumen episodico de A"
        assert body["procedural"]["items"][0]["key"] == "pref.A"

        _assert_no_raw_blob(body)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. GET /memory?layer=semantic → solo semantic, paginado (limit/offset)
# ---------------------------------------------------------------------------


async def test_list_memory_filtered_by_layer_paginated(db_session: AsyncSession) -> None:
    """?layer=semantic devuelve solo la rama semantic; limit/offset paginan."""
    user = await _seed_user(db_session)
    semantic, _, _ = _stores(db_session, user.id)
    # 3 hechos semánticos para ejercitar la paginación.
    for i in range(3):
        await semantic.add(SemanticMemoryCreate(content=f"hecho numero {i}"))
    await db_session.flush()

    client = await _client(db_session)
    try:
        async with client:
            # Página 1: limit=2 → 2 items, total=3.
            resp1 = await client.get(
                "/v1/memory?layer=semantic&limit=2&offset=0", headers=_bearer(user.id)
            )
            # Página 2: offset=2 → 1 item restante.
            resp2 = await client.get(
                "/v1/memory?layer=semantic&limit=2&offset=2", headers=_bearer(user.id)
            )

        assert resp1.status_code == 200
        body1 = resp1.json()
        # Rama directa (no agrupada): tiene items + total, no las 3 capas.
        assert set(body1.keys()) == {"items", "total"}
        assert body1["total"] == 3
        assert len(body1["items"]) == 2

        body2 = resp2.json()
        assert body2["total"] == 3
        assert len(body2["items"]) == 1

        # Las dos páginas no se solapan (ids distintos).
        ids_p1 = {it["id"] for it in body1["items"]}
        ids_p2 = {it["id"] for it in body2["items"]}
        assert ids_p1.isdisjoint(ids_p2)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. GET /memory/semantic/{id} propio → 200 content descifrado + metadata
# ---------------------------------------------------------------------------


async def test_get_own_semantic_item(db_session: AsyncSession) -> None:
    """200 con content descifrado y la metadata sagrada (importance, timestamps)."""
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="X")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(
                f"/v1/memory/semantic/{refs['semantic_id']}", headers=_bearer(user.id)
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(refs["semantic_id"])
        assert body["content"] == "hecho semantico de X"
        assert body["user_id"] == str(user.id)
        # Metadata presente (los campos del *Out sagrado).
        assert "created_at" in body
        assert "updated_at" in body
        assert "importance" in body
        assert "source_session_id" in body
        _assert_no_raw_blob(body)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. AISLAMIENTO CLAVE: item de OTRO user → 404 (no 200, no leak)
# ---------------------------------------------------------------------------


async def test_get_other_users_item_returns_404_no_oracle(db_session: AsyncSession) -> None:
    """El item del owner consultado por un intruder da 404 (ajena == inexistente).

    Es el test SAGRADO: un GET de la memoria de otro user NUNCA devuelve 200 ni
    filtra el content. Mismo 404 (status + detail) que un id inexistente. Se cubre
    semantic (UUID) y procedural (key).
    """
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, owner, tag="OWNER")

    client = await _client(db_session)
    try:
        async with client:
            # El intruder usa el id semantic REAL del owner.
            resp_sem = await client.get(
                f"/v1/memory/semantic/{refs['semantic_id']}", headers=_bearer(intruder.id)
            )
            # El intruder usa la key procedural REAL del owner.
            resp_proc = await client.get(
                f"/v1/memory/procedural/{refs['procedural_key']}",
                headers=_bearer(intruder.id),
            )
            # El intruder usa el id episodico REAL del owner.
            resp_epi = await client.get(
                f"/v1/memory/episodic/{refs['episodic_id']}", headers=_bearer(intruder.id)
            )

        # 404 en las 3 capas: nada del owner se filtra.
        assert resp_sem.status_code == 404
        assert resp_proc.status_code == 404
        assert resp_epi.status_code == 404
        # El detail no revela existencia ajena: es el genérico.
        assert resp_sem.json()["detail"] == "memoria no encontrada"
        assert resp_proc.json()["detail"] == "memoria no encontrada"
        # El content del owner NO aparece en ninguna respuesta del intruder.
        assert "OWNER" not in resp_sem.text
        assert "OWNER" not in resp_proc.text
        assert "OWNER" not in resp_epi.text
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. GET /memory/semantic/{uuid inexistente} → 404 (mismo detail que ajena)
# ---------------------------------------------------------------------------


async def test_get_nonexistent_item_same_404(db_session: AsyncSession) -> None:
    """Un UUID random inexistente da el MISMO 404 (status + detail) que la ajena."""
    user = await _seed_user(db_session)
    nonexistent = uuid.uuid4()

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(f"/v1/memory/semantic/{nonexistent}", headers=_bearer(user.id))

        assert resp.status_code == 404
        assert resp.json()["detail"] == "memoria no encontrada"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. GET /memory/export → 3 capas SOLO de A, descifradas, version + attachment
# ---------------------------------------------------------------------------


async def test_export_only_own_versioned_attachment(db_session: AsyncSession) -> None:
    """Export: 3 capas completas SOLO del user, version+exported_at, Content-Disposition."""
    user_a = await _seed_user(db_session)
    user_b = await _seed_user(db_session)
    await _seed_full_memory(db_session, user_a, tag="A")
    await _seed_full_memory(db_session, user_b, tag="B")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/memory/export", headers=_bearer(user_a.id))

        assert resp.status_code == 200
        # Header de descarga.
        assert (
            resp.headers["content-disposition"] == 'attachment; filename="ynara-memory-export.json"'
        )
        body = resp.json()
        assert body["version"] == 1
        assert "exported_at" in body

        # Las 3 capas, solo de A (content descifrado, tag A; nada de B).
        assert len(body["semantic"]) == 1
        assert body["semantic"][0]["content"] == "hecho semantico de A"
        assert len(body["episodic"]) == 1
        assert body["episodic"][0]["summary"] == "resumen episodico de A"
        assert len(body["procedural"]) == 1
        assert body["procedural"][0]["key"] == "pref.A"

        # Nada de B se coló en el export de A.
        assert "de B" not in resp.text
        assert "pref.B" not in resp.text
        _assert_no_raw_blob(body)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. limit fuera de rango → 422; ref no-UUID en semantic → 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_limit", [0, 101])
async def test_limit_out_of_range_422(db_session: AsyncSession, bad_limit: int) -> None:
    """limit=0 o limit=101 → 422 (FastAPI valida el Query ge=1 le=100)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(f"/v1/memory?limit={bad_limit}", headers=_bearer(user.id))
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_non_uuid_ref_in_semantic_422(db_session: AsyncSession) -> None:
    """ref no-UUID en semantic → 422 (no 404: es un error de forma, no de existencia)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get("/v1/memory/semantic/no-es-un-uuid", headers=_bearer(user.id))
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_invalid_layer_422(db_session: AsyncSession) -> None:
    """Una capa que no existe en el enum → 422 (el path param es MemoryLayer)."""
    user = await _seed_user(db_session)

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.get(
                f"/v1/memory/inexistente/{uuid.uuid4()}", headers=_bearer(user.id)
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. sin token → 401
# ---------------------------------------------------------------------------


async def test_no_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 en los 3 GET (get_current_user)."""
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="Z")

    client = await _client(db_session)
    try:
        async with client:
            r_list = await client.get("/v1/memory")
            r_item = await client.get(f"/v1/memory/semantic/{refs['semantic_id']}")
            r_export = await client.get("/v1/memory/export")
        assert r_list.status_code == 401
        assert r_item.status_code == 401
        assert r_export.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ===========================================================================
# OLA 2 — MUTACIÓN INDIVIDUAL (PATCH / DELETE). Aislamiento + ownership + 405.
# ===========================================================================


# ---------------------------------------------------------------------------
# OLA2-1. PATCH semantic propio → content actualizado (respuesta + GET reflejan)
# ---------------------------------------------------------------------------


async def test_patch_own_semantic_updates_content(db_session: AsyncSession) -> None:
    """PATCH semantic propio: la respuesta trae el content nuevo y un GET posterior
    también (re-cifrado round-trip de punta a punta)."""
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="P1")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/memory/semantic/{refs['semantic_id']}",
                json={"content": "hecho semantico EDITADO"},
                headers=_bearer(user.id),
            )
            # GET posterior en la MISMA sesión: refleja el cambio re-cifrado.
            after = await client.get(
                f"/v1/memory/semantic/{refs['semantic_id']}", headers=_bearer(user.id)
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(refs["semantic_id"])
        assert body["content"] == "hecho semantico EDITADO"
        assert body["user_id"] == str(user.id)
        _assert_no_raw_blob(body)

        assert after.status_code == 200
        assert after.json()["content"] == "hecho semantico EDITADO"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-2. PATCH procedural propio → value actualizado (sin crear, key existente)
# ---------------------------------------------------------------------------


async def test_patch_own_procedural_updates_value(db_session: AsyncSession) -> None:
    """PATCH procedural propio: el value JSONB se reemplaza; un GET posterior lo refleja."""
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="P2")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/memory/procedural/{refs['procedural_key']}",
                json={"value": {"nuevo": "valor", "n": 7}},
                headers=_bearer(user.id),
            )
            after = await client.get(
                f"/v1/memory/procedural/{refs['procedural_key']}", headers=_bearer(user.id)
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["key"] == refs["procedural_key"]
        assert body["value"] == {"nuevo": "valor", "n": 7}

        assert after.status_code == 200
        assert after.json()["value"] == {"nuevo": "valor", "n": 7}
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-3. PATCH episodic → 405 (el summary no se edita a mano)
# ---------------------------------------------------------------------------


async def test_patch_episodic_405(db_session: AsyncSession) -> None:
    """PATCH episodic → 405 Method Not Allowed (no 404, no 200)."""
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="P3")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/memory/episodic/{refs['episodic_id']}",
                json={"content": "no deberia poder editar el resumen"},
                headers=_bearer(user.id),
            )
            # El episodio sigue intacto (el summary original no cambió).
            after = await client.get(
                f"/v1/memory/episodic/{refs['episodic_id']}", headers=_bearer(user.id)
            )

        assert resp.status_code == 405
        assert after.status_code == 200
        assert after.json()["summary"] == "resumen episodico de P3"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-4. AISLAMIENTO: PATCH semantic de OTRO user → 404 (no muta, sin leak)
# ---------------------------------------------------------------------------


async def test_patch_other_users_semantic_404_no_mutation(db_session: AsyncSession) -> None:
    """PATCH del item semantic de otro user → 404; el item del owner NO se mutó."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, owner, tag="OWNER")

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                f"/v1/memory/semantic/{refs['semantic_id']}",
                json={"content": "INYECTADO por el intruder"},
                headers=_bearer(intruder.id),
            )
            # El owner relee su item: sigue con el content original, intacto.
            owner_get = await client.get(
                f"/v1/memory/semantic/{refs['semantic_id']}", headers=_bearer(owner.id)
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "memoria no encontrada"
        # Ni el content del owner ni el inyectado se filtran en la respuesta.
        assert "OWNER" not in resp.text
        assert "INYECTADO" not in resp.text

        # El item del owner no fue tocado.
        assert owner_get.status_code == 200
        assert owner_get.json()["content"] == "hecho semantico de OWNER"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-5. PATCH procedural de key inexistente → 404 (NO crea vía upsert)
# ---------------------------------------------------------------------------


async def test_patch_procedural_nonexistent_key_404_no_create(db_session: AsyncSession) -> None:
    """PATCH sobre una key procedural inexistente → 404; NO se crea la entrada."""
    user = await _seed_user(db_session)
    # El user no tiene ninguna preferencia sembrada.

    client = await _client(db_session)
    try:
        async with client:
            resp = await client.patch(
                "/v1/memory/procedural/pref.inexistente",
                json={"value": {"no": "deberia crearse"}},
                headers=_bearer(user.id),
            )
            # Un GET confirma que la key NO fue creada por el PATCH.
            after = await client.get(
                "/v1/memory/procedural/pref.inexistente", headers=_bearer(user.id)
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "memoria no encontrada"
        assert after.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-6. PATCH con body que NO corresponde a la capa → 422
# ---------------------------------------------------------------------------


async def test_patch_body_mismatch_422(db_session: AsyncSession) -> None:
    """semantic sin 'content' → 422; procedural sin 'value' → 422 (body no aplica)."""
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="P6")

    client = await _client(db_session)
    try:
        async with client:
            # semantic con body de procedural (value, sin content) → 422.
            r_sem = await client.patch(
                f"/v1/memory/semantic/{refs['semantic_id']}",
                json={"value": {"x": 1}},
                headers=_bearer(user.id),
            )
            # procedural con body de semantic (content, sin value) → 422.
            r_proc = await client.patch(
                f"/v1/memory/procedural/{refs['procedural_key']}",
                json={"content": "soy content, no value"},
                headers=_bearer(user.id),
            )

        assert r_sem.status_code == 422
        assert r_proc.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-7. DELETE propio (3 capas) → 204; GET posterior → 404
# ---------------------------------------------------------------------------


async def test_delete_own_three_layers_204_then_404(db_session: AsyncSession) -> None:
    """DELETE de semantic/episodic/procedural propios → 204 sin body; luego GET → 404."""
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="DEL")

    client = await _client(db_session)
    try:
        async with client:
            d_sem = await client.delete(
                f"/v1/memory/semantic/{refs['semantic_id']}", headers=_bearer(user.id)
            )
            d_epi = await client.delete(
                f"/v1/memory/episodic/{refs['episodic_id']}", headers=_bearer(user.id)
            )
            d_proc = await client.delete(
                f"/v1/memory/procedural/{refs['procedural_key']}", headers=_bearer(user.id)
            )

            g_sem = await client.get(
                f"/v1/memory/semantic/{refs['semantic_id']}", headers=_bearer(user.id)
            )
            g_epi = await client.get(
                f"/v1/memory/episodic/{refs['episodic_id']}", headers=_bearer(user.id)
            )
            g_proc = await client.get(
                f"/v1/memory/procedural/{refs['procedural_key']}", headers=_bearer(user.id)
            )

        # 204 sin body en las 3 capas.
        assert d_sem.status_code == 204
        assert d_epi.status_code == 204
        assert d_proc.status_code == 204
        assert d_sem.content == b""
        assert d_epi.content == b""
        assert d_proc.content == b""

        # Ya no existen.
        assert g_sem.status_code == 404
        assert g_epi.status_code == 404
        assert g_proc.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-8. AISLAMIENTO: DELETE de OTRO user (id/key real del owner) → 404; sobrevive
# ---------------------------------------------------------------------------


async def test_delete_other_users_404_owner_survives(db_session: AsyncSession) -> None:
    """DELETE con id/key REAL del owner pero JWT del intruder → 404; el owner sigue
    teniendo su memoria intacta (no se borró)."""
    owner = await _seed_user(db_session)
    intruder = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, owner, tag="SURV")

    client = await _client(db_session)
    try:
        async with client:
            d_sem = await client.delete(
                f"/v1/memory/semantic/{refs['semantic_id']}", headers=_bearer(intruder.id)
            )
            d_epi = await client.delete(
                f"/v1/memory/episodic/{refs['episodic_id']}", headers=_bearer(intruder.id)
            )
            d_proc = await client.delete(
                f"/v1/memory/procedural/{refs['procedural_key']}", headers=_bearer(intruder.id)
            )

            # El owner relee: sus 3 ítems siguen existiendo.
            g_sem = await client.get(
                f"/v1/memory/semantic/{refs['semantic_id']}", headers=_bearer(owner.id)
            )
            g_epi = await client.get(
                f"/v1/memory/episodic/{refs['episodic_id']}", headers=_bearer(owner.id)
            )
            g_proc = await client.get(
                f"/v1/memory/procedural/{refs['procedural_key']}", headers=_bearer(owner.id)
            )

        # El intruder recibe 404 en las 3 capas (ajena == inexistente).
        assert d_sem.status_code == 404
        assert d_epi.status_code == 404
        assert d_proc.status_code == 404
        assert d_sem.json()["detail"] == "memoria no encontrada"

        # La memoria del owner sigue intacta: no se borró nada ajeno.
        assert g_sem.status_code == 200
        assert g_sem.json()["content"] == "hecho semantico de SURV"
        assert g_epi.status_code == 200
        assert g_proc.status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-9. DELETE inexistente → 404
# ---------------------------------------------------------------------------


async def test_delete_nonexistent_404(db_session: AsyncSession) -> None:
    """DELETE de un id/key inexistente → 404 (mismo detail que ajena)."""
    user = await _seed_user(db_session)
    nonexistent = uuid.uuid4()

    client = await _client(db_session)
    try:
        async with client:
            d_sem = await client.delete(
                f"/v1/memory/semantic/{nonexistent}", headers=_bearer(user.id)
            )
            d_proc = await client.delete(
                "/v1/memory/procedural/pref.no-existe", headers=_bearer(user.id)
            )

        assert d_sem.status_code == 404
        assert d_sem.json()["detail"] == "memoria no encontrada"
        assert d_proc.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-10. sin token → 401 (PATCH + DELETE)
# ---------------------------------------------------------------------------


async def test_patch_delete_no_token_401(db_session: AsyncSession) -> None:
    """Sin Authorization header → 401 en PATCH y DELETE (get_current_user)."""
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="NT")

    client = await _client(db_session)
    try:
        async with client:
            r_patch = await client.patch(
                f"/v1/memory/semantic/{refs['semantic_id']}",
                json={"content": "x"},
            )
            r_delete = await client.delete(f"/v1/memory/semantic/{refs['semantic_id']}")
        assert r_patch.status_code == 401
        assert r_delete.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OLA2-11. REGRESION: el endpoint mutante DEBE commitear (persistencia en prod)
# ---------------------------------------------------------------------------


async def test_patch_delete_commit_only_on_success(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATCH/DELETE exitoso DEBE ``await session.commit()``; un 404 NO commitea.

    Regresión del bug de Ola 2: los stores solo hacen ``flush()`` y ``get_db`` no
    commitea (cierra -> rollback), así que sin un ``commit`` explícito en el endpoint
    la mutación NO persiste en prod. Los tests con sesión compartida no lo detectaban.
    Acá se cuentan los ``commit`` con un spy no-op (no commitea de verdad -> el assert
    no depende del aislamiento del fixture) y se verifica que el happy path commitea y
    que un 404 no.
    """
    user = await _seed_user(db_session)
    refs = await _seed_full_memory(db_session, user, tag="CMT")

    commits = 0

    async def _spy_commit() -> None:
        nonlocal commits
        commits += 1  # no-op deliberado: solo contamos la intención de persistir.

    monkeypatch.setattr(db_session, "commit", _spy_commit)

    client = await _client(db_session)
    try:
        async with client:
            # PATCH semantic propio (éxito) -> 1 commit.
            ok = await client.patch(
                f"/v1/memory/semantic/{refs['semantic_id']}",
                json={"content": "editado"},
                headers=_bearer(user.id),
            )
            assert ok.status_code == 200
            assert commits == 1, "PATCH exitoso debe commitear"

            # PATCH a un id inexistente (404) -> NO commitea (no mutó nada).
            miss = await client.patch(
                f"/v1/memory/semantic/{uuid.uuid4()}",
                json={"content": "no aplica"},
                headers=_bearer(user.id),
            )
            assert miss.status_code == 404
            assert commits == 1, "un 404 no muta nada y no debe commitear"

            # DELETE procedural propio (éxito) -> 1 commit más.
            dele = await client.delete(
                f"/v1/memory/procedural/{refs['procedural_key']}",
                headers=_bearer(user.id),
            )
            assert dele.status_code == 204
            assert commits == 2, "DELETE exitoso debe commitear"
    finally:
        app.dependency_overrides.clear()
