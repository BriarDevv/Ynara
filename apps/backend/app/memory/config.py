"""Carga y validacion de los thresholds de memoria (ADR-007 D1).

Parsea el sub-bloque de decay de ``ynara.config.json[memory]`` y lo expone
como un objeto inmutable. Espeja 1:1 la mecanica de ``app/llm/config.py``
(Pydantic frozen + strict + ``extra='forbid'`` + fail-fast envuelto en un
error tipado + cache ``lru_cache`` por modulo + inyectable para tests).

A diferencia del loader de LLM, el de memoria es **default-safe**: si el
bloque ``[memory]`` no trae las keys de decay (config viejo, anterior a
#211), ``load_decay_config()`` devuelve ``DecayConfig()`` con los defaults
de ADR-007 D1 y NO rompe. Solo levanta ``MemoryConfigError`` cuando el
bloque existe pero un valor es invalido (factor > 1, dias <= 0, tipo
erroneo, key extra) o cuando la combinacion de thresholds es incoherente
(``hard_delete_threshold > stale_threshold``).

Este modulo es un sibling de COMPORTAMIENTO de las tablas sagradas
(``semantic``/``episodic``/``procedural``/``audit``): parsea config, no toca
columnas. Es el punto de extension unico para las keys de ``[memory]``: ademas
del decay (ADR-007 D1) expone ``RetentionConfig`` (ADR-007 D2), que parsea las
4 keys de retention episodica con el MISMO patron (frozen/strict/extra='forbid'
+ default-safe + fail-fast envuelto en ``MemoryConfigError``).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

# ``config.py`` vive en apps/backend/app/memory/; la raiz del repo esta 4
# niveles arriba (memory -> app -> backend -> apps -> repo root). Mismo
# calculo que ``app/llm/config.py`` (ambos cuelgan de apps/backend/app/<pkg>/).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_PATH = _REPO_ROOT / "ynara.config.json"


class MemoryConfigError(RuntimeError):
    """Config de memoria incoherente o ilegible. Fail-fast, espejo de LlmConfigError."""


class DecayConfig(BaseModel):
    """Thresholds del decay procedural (``ynara.config.json[memory]``, ADR-007 D1).

    Defaults = valores que estaban hardcodeados en ``app/workflows/decay.py``
    antes de #211 (criterio: no alterar comportamiento). ``strict`` +
    ``frozen`` + ``extra='forbid'`` atrapan typos de operador en deploy
    (fail-fast) sin tumbar el worker: el ``try/except`` del task Celery sigue
    siendo la red final.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    decay_interval_days: int = Field(default=14, gt=0)
    decay_factor: float = Field(default=0.9, gt=0, le=1)
    stale_threshold: float = Field(default=0.3, gt=0, le=1)
    hard_delete_threshold: float = Field(default=0.1, gt=0, le=1)
    hard_delete_min_days: int = Field(default=90, gt=0)

    @model_validator(mode="after")
    def _check_thresholds_ordered(self) -> DecayConfig:
        """``hard_delete_threshold`` debe quedar bajo ``stale_threshold``.

        Si el umbral de hard-delete queda por encima del de stale, se borrarian
        entradas que nunca llegaron a marcarse stale: rompe la semantica de los
        tres pasos (decay -> stale -> hard-delete). Cross-field que Pydantic no
        valida campo a campo.
        """
        if self.hard_delete_threshold > self.stale_threshold:
            raise ValueError(
                "hard_delete_threshold "
                f"({self.hard_delete_threshold}) no puede superar stale_threshold "
                f"({self.stale_threshold}): rompe la semantica de los 3 pasos del decay"
            )
        return self


class RetentionConfig(BaseModel):
    """Retention episodica diferenciada (``ynara.config.json[memory]``, ADR-007 D2).

    Defaults = valores que estaban hardcodeados en ``app/workflows/consolidation.py``
    (criterio: no alterar comportamiento; ``retention_default_days=365``,
    ``retention_sensitive_days=180``). ``sensitive`` es la retention por defecto de
    las entradas en modo Bienestar (``is_sensitive=True``); el rango
    ``[min, max]`` espeja el rango configurable por usuario via
    ``PATCH /v1/memory/settings`` (constraint ``users.retention_sensitive_days
    BETWEEN 30 AND 365``). El cap duro ``<=365`` para entradas sensibles lo sigue
    enforzando el ``model_validator`` de ``EpisodicMemoryCreate`` + la CHECK
    constraint (ADR-007 D2); aca solo se valida la coherencia del bloque de config.

    Mismo contrato que ``DecayConfig``: ``strict`` + ``frozen`` + ``extra='forbid'``
    atrapan typos de operador en deploy (fail-fast) sin tumbar el worker (el
    ``try/except`` del task Celery sigue siendo la red final).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    retention_default_days: int = Field(default=365, gt=0)
    retention_sensitive_days: int = Field(default=180, gt=0)
    retention_sensitive_min_days: int = Field(default=30, gt=0)
    retention_sensitive_max_days: int = Field(default=365, gt=0)
    # Cadencia (en dias) del worker de retention episodica (beat). NO es un periodo
    # de retention: es cada cuanto corre ``purge_episodic_memory`` para borrar los
    # episodios vencidos (``created_at + retention_days < now``). Default 1 (diario)
    # por privacidad — los episodios sensibles vencidos se borran pronto — pero es
    # configurable (operador puede subirlo). Cadencia, no compounding: a diferencia
    # del decay (14d para evitar compounding sin ``last_decayed_at``), la retention
    # solo borra lo ya vencido, asi que correrla mas seguido es inocuo. Cap ``<=30``
    # (mensual): una cadencia mayor dejaria los episodios sensibles vencidos vivos
    # demasiado tiempo (hasta retention_days + interval); el cap es una guarda de
    # privacidad contra una misconfiguracion (espeja el cap duro de las otras keys).
    episodic_retention_interval_days: int = Field(default=1, gt=0, le=30)

    @model_validator(mode="after")
    def _check_retention_coherent(self) -> RetentionConfig:
        """El rango sensible debe ser coherente y la sensible default caer dentro.

        Tres invariantes cross-field que Pydantic no valida campo a campo:

        - ``min <= max``: un rango invertido no tiene semantica.
        - ``max <= 365``: el cap de ADR-007 D2 para entradas sensibles (espejo de la
          CHECK constraint ``users.retention_sensitive_days BETWEEN 30 AND 365``); un
          ``max`` mayor permitiria configurar retention sensible sobre el limite.
        - ``min <= sensitive <= max``: la retention sensible por defecto debe caer
          dentro del rango configurable, si no el default ya seria invalido.
        """
        if self.retention_sensitive_min_days > self.retention_sensitive_max_days:
            raise ValueError(
                "retention_sensitive_min_days "
                f"({self.retention_sensitive_min_days}) no puede superar "
                f"retention_sensitive_max_days ({self.retention_sensitive_max_days})"
            )
        if self.retention_sensitive_max_days > 365:
            raise ValueError(
                "retention_sensitive_max_days "
                f"({self.retention_sensitive_max_days}) no puede superar 365 "
                "(cap de ADR-007 D2 para entradas sensibles)"
            )
        if not (
            self.retention_sensitive_min_days
            <= self.retention_sensitive_days
            <= self.retention_sensitive_max_days
        ):
            raise ValueError(
                "retention_sensitive_days "
                f"({self.retention_sensitive_days}) debe caer dentro del rango "
                f"[{self.retention_sensitive_min_days}, {self.retention_sensitive_max_days}]"
            )
        return self


def _read_config_file(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MemoryConfigError(f"no se pudo leer {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MemoryConfigError(f"{path} no es JSON valido: {exc}") from exc
    if not isinstance(data, dict):
        raise MemoryConfigError(f"{path} debe ser un objeto JSON en el top-level")
    return data


# Keys propias de cada sub-config dentro del bloque ``[memory]``. Las demas keys
# del bloque (engine/store/embedding_model/consolidation y las keys del OTRO
# sub-config) NO pertenecen al modelo y se ignoran al construirlo: ``extra='forbid'``
# aplica sobre el sub-conjunto de keys del modelo, no sobre todo ``[memory]``.
_DECAY_KEYS = frozenset(DecayConfig.model_fields)
_RETENTION_KEYS = frozenset(RetentionConfig.model_fields)


def _build_sub_config[T: (DecayConfig, RetentionConfig)](
    data: dict[str, object],
    *,
    model: type[T],
    keys: frozenset[str],
) -> T:
    """Construye un sub-config de ``[memory]`` (decay o retention) default-safe.

    Filtra el bloque ``[memory]`` a las ``keys`` del modelo y lo valida. Si el
    bloque falta, no es dict, o no trae ninguna de esas keys (config viejo),
    devuelve el modelo con sus defaults (NO rompe). Si trae keys pero un valor es
    invalido, envuelve el ``ValidationError`` en ``MemoryConfigError`` (fail-fast).
    """
    raw_memory = data.get("memory")
    # Bloque [memory] ausente o no-dict -> defaults (compat con config viejo).
    if not isinstance(raw_memory, dict):
        return model()

    # Solo las keys del modelo; el resto del bloque [memory] no es asunto suyo.
    values = {key: value for key, value in raw_memory.items() if key in keys}
    # Ninguna key del modelo presente -> defaults (config viejo).
    if not values:
        return model()

    try:
        return model.model_validate(values)
    except ValidationError as exc:
        # Envolvemos para que el caller solo atrape MemoryConfigError.
        raise MemoryConfigError(f"ynara.config.json[memory] invalido: {exc}") from exc


def _build_decay_config(data: dict[str, object]) -> DecayConfig:
    return _build_sub_config(data, model=DecayConfig, keys=_DECAY_KEYS)


def _build_retention_config(data: dict[str, object]) -> RetentionConfig:
    return _build_sub_config(data, model=RetentionConfig, keys=_RETENTION_KEYS)


def load_decay_config(*, config_path: Path | None = None) -> DecayConfig:
    """Carga y valida los thresholds de decay de ``ynara.config.json[memory]``.

    Inyectable para tests (``config_path``); sin argumentos usa
    ``ynara.config.json`` de la raiz del repo y cachea el resultado. Es
    default-safe: si el bloque ``[memory]`` no trae las keys de decay devuelve
    ``DecayConfig()`` (defaults de ADR-007 D1) y NO rompe.
    """
    if config_path is None:
        return _load_cached_decay()
    return _build_decay_config(_read_config_file(config_path))


def load_retention_config(*, config_path: Path | None = None) -> RetentionConfig:
    """Carga y valida la retention episodica de ``ynara.config.json[memory]``.

    Espejo de ``load_decay_config`` para las keys de retention (ADR-007 D2).
    Inyectable para tests (``config_path``); sin argumentos usa
    ``ynara.config.json`` de la raiz del repo y cachea el resultado. Es
    default-safe: si el bloque ``[memory]`` no trae las keys de retention devuelve
    ``RetentionConfig()`` (defaults de ADR-007 D2: default=365, sensitive=180) y
    NO rompe.
    """
    if config_path is None:
        return _load_cached_retention()
    return _build_retention_config(_read_config_file(config_path))


@lru_cache(maxsize=1)
def _load_cached_decay() -> DecayConfig:
    return _build_decay_config(_read_config_file(_CONFIG_PATH))


@lru_cache(maxsize=1)
def _load_cached_retention() -> RetentionConfig:
    return _build_retention_config(_read_config_file(_CONFIG_PATH))
