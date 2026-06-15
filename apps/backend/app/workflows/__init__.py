"""Workflows complejos: consolidación de memoria, generación de
resúmenes episódicos, decaimiento de procedural, etc.

Convención: un módulo por workflow. Tasks Celery se declaran con
``@celery_app.task`` y se documentan en docstring.

Los módulos de tasks se importan acá para que importar el paquete
``app.workflows`` registre TODAS las ``@celery_app.task``. El autodiscovery de
Celery (``celery_app.autodiscover_tasks(packages=["app.workflows"])``) usa el
``related_name`` default ``"tasks"`` y busca un ``app.workflows.tasks``
inexistente; pero ``find_related_module`` importa primero el paquete
(``import_module("app.workflows")``), que corre este ``__init__``. Sin estos
imports el worker arrancaba con el registro vacío y rechazaba cada task encolada
(``Received unregistered task 'workflows.consolidate_turn'``). Los módulos se
re-exportan vía ``__all__`` para que el linter no los marque como no usados (F401).
"""

from app.workflows import audit_retention, consolidation, decay

__all__ = ["audit_retention", "consolidation", "decay"]
