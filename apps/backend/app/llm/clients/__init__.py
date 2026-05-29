"""Clientes de inferencia LLM.

- ``base`` define los Protocols (``LLMClient``, ``ToolCallParser``).
- ``vllm`` implementa el cliente HTTP contra un proceso vLLM
  OpenAI-compatible.
- ``parsers`` normaliza las tool calls del formato OpenAI que devuelve vLLM.
- ``fakes`` provee un cliente programable para tests del router / pool.

El router (``router.py``) solo conoce el Protocol ``LLMClient``, nunca la
implementacion concreta (ADR-009 D1).
"""
