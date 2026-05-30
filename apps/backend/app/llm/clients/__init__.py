"""Clientes de inferencia LLM.

- ``base`` define los Protocols (``LLMClient``, ``ToolCallParser``).
- ``vllm`` implementa el cliente HTTP contra un proceso vLLM
  OpenAI-compatible.
- ``parsers`` normaliza las tool calls del formato OpenAI que devuelve vLLM.
- ``fakes`` provee un cliente programable para tests del router / pool.
- ``circuit`` implementa el ``CircuitBreaker`` por instancia (M3).
- ``pool`` agrupa clientes y rutea por modelo (``ClientPool`` +
  ``RoutingStrategy``).
- ``resilient`` envuelve el pool con retry + breaker + fallback on-prem
  (``ResilientClient``).
- ``embedding`` define el Protocol ``EmbeddingClient`` y el
  ``FakeEmbeddingClient`` determinista que consumen los wrappers de memoria (M7).

El router (``router.py``) solo conoce el Protocol ``LLMClient``, nunca la
implementacion concreta (ADR-009 D1).
"""
