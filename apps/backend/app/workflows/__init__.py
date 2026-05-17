"""Workflows complejos: consolidación de memoria, generación de
resúmenes episódicos, decaimiento de procedural, etc.

Convención: un módulo por workflow. Tasks Celery se declaran con
``@celery_app.task`` y se documentan en docstring.
"""
