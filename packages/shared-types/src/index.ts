// Types compartidos entre web y mobile.
// Mantener coherentes con los Pydantic schemas en apps/backend/.

export type Mode =
  | "productividad"
  | "estudio"
  | "bienestar"
  | "vida"
  | "memoria";

export type MemoryLayer = "semantic" | "episodic" | "procedural";

export type Tone =
  | "neutro-eficaz"
  | "encouragement"
  | "casual-empatico"
  | "casual-rioplatense";

export type ModelRole = "conversational" | "agent";

export interface ModeConfig {
  model: string;
  memory_layers: MemoryLayer[];
  tools_enabled: string[];
  tone: Tone;
}

// TODO: agregar types de Chat, Memory, Session, Auth cuando se cierren.
