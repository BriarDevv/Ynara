"""Tests de ``resolve_config_path``: env override → walk-up → fallback CWD.

Cubre la resolución robusta del path de ``ynara.config.json`` que reemplazó al
``parents[4]`` frágil (rompía en el contenedor con IndexError).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import paths
from app.core.paths import resolve_config_path


def test_env_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``YNARA_CONFIG_PATH`` tiene prioridad sobre el walk-up (lo que setea la imagen)."""
    cfg = tmp_path / "custom-ynara.json"
    monkeypatch.setenv("YNARA_CONFIG_PATH", str(cfg))
    assert resolve_config_path() == cfg


def test_walk_up_finds_repo_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin env, el walk-up encuentra el ``ynara.config.json`` real (raíz del repo)."""
    monkeypatch.delenv("YNARA_CONFIG_PATH", raising=False)
    resolved = resolve_config_path()
    assert resolved.name == "ynara.config.json"
    assert resolved.exists()


def test_fallback_to_cwd_when_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si ni el env ni el walk-up resuelven, cae a ``CWD/ynara.config.json``."""
    monkeypatch.delenv("YNARA_CONFIG_PATH", raising=False)
    # Nombre inexistente: el walk-up no matchea ningún ancestro -> fallback a CWD.
    monkeypatch.setattr(paths, "_CONFIG_FILENAME", "__no_existe_ynara__.json")
    assert resolve_config_path() == Path.cwd() / "__no_existe_ynara__.json"
