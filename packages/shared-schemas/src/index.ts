import { z } from "zod";

export const ModeSchema = z.enum([
  "productividad",
  "estudio",
  "bienestar",
  "vida",
  "memoria",
]);
export type Mode = z.infer<typeof ModeSchema>;

export const MemoryLayerSchema = z.enum([
  "semantic",
  "episodic",
  "procedural",
]);
export type MemoryLayer = z.infer<typeof MemoryLayerSchema>;

// TODO: agregar ChatRequest, ChatResponse, MemoryEntry, AuthLogin,
// etc. cuando los Pydantic schemas del backend estén cerrados.
