"""Tests del backend de Ynara.

Pytest async (`pytest-asyncio`). Fixtures comunes viven en
``conftest.py``.

Política: tests de DB usan una base de datos **real** (de tests), no
mocks. Tests de migración corren `alembic upgrade head` contra esa DB.
"""
