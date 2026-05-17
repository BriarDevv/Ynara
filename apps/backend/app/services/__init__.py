"""Capa de servicios (lógica de negocio).

Convención: un módulo por dominio. Los servicios reciben sus
dependencias (sesión DB, clientes HTTP, etc.) por argumento; **no**
importan de FastAPI ni instancian engines globales. Esto los hace
fácilmente testeables.
"""
