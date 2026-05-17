"""Capa LLM de Ynara.

- ``router`` decide qué modelo usar según el modo activo.
- ``prompts`` contiene los prompt templates por modo.
- ``tools`` contiene las tools que Qwen puede llamar.

Reglas:
- Gemma 4 26B-A4B → modos conversacionales. Solo lee memoria.
- Qwen 3.5-9B → modos agente. Lee y escribe memoria, llama tools.
- Ningún dato de usuario sale del perímetro (regla #4 de AGENTS.md).
"""
