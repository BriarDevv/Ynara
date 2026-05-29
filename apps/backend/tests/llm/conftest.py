"""Fixtures de los tests de la capa LLM.

``app.core.config`` instancia ``settings = get_settings()`` a nivel de
modulo, lo que requiere ``DATABASE_URL`` / ``REDIS_URL`` / ``JWT_SECRET``
presentes al importar. Los seteamos aca con valores dummy ANTES de que
pytest importe cualquier modulo de ``app`` (este conftest corre primero),
para que la coleccion no rompa sin un ``.env`` real. No tocan red ni DB.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-no-usar-en-prod")
