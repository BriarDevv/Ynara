import type {
  EpisodicMemoryOut,
  MemoryList,
  ProceduralMemoryOut,
  SemanticMemoryOut,
} from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";
import { presentDetail } from "./detail-presenter";
import { relatedEntries, sessionRefOf } from "./timeline";

const ISO = "2026-05-08T09:42:00.000Z";
const UUID = "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const SESSION = "0193ffff-bbbb-cccc-dddd-eeeeeeeeeeee";

const semantic: SemanticMemoryOut = {
  id: UUID,
  user_id: UUID,
  content: "Decidiste arrancar por el capítulo 3.",
  importance: 80,
  source_session_id: SESSION,
  created_at: ISO,
  updated_at: ISO,
};

const episodic: EpisodicMemoryOut = {
  id: `${UUID}`,
  user_id: UUID,
  session_id: SESSION,
  summary: "Charla sobre el brief.",
  is_sensitive: true,
  retention_days: 365,
  occurred_at: ISO,
  topics: { proyecto: "omi" },
  created_at: ISO,
  updated_at: ISO,
};

const procedural: ProceduralMemoryOut = {
  id: UUID,
  user_id: UUID,
  key: "foco_horario",
  value: { preferencia: "mañana" },
  confidence: 0.86,
  last_reinforced_at: ISO,
  stale: true,
  created_at: ISO,
  updated_at: ISO,
};

describe("presentDetail", () => {
  it("semántica: quote = content, fromSession según source_session_id", () => {
    const p = presentDetail("semantic", semantic);
    expect(p.quote).toBe(semantic.content);
    expect(p.fromSession).toBe(true);
    expect(p.meta).toContainEqual({ label: "Importancia", value: "80/100" });
  });

  it("episódica: marca recuerdo sensible y mapea topics a tags", () => {
    const p = presentDetail("episodic", episodic);
    expect(p.quote).toBe(episodic.summary);
    expect(p.note).toMatch(/sensible/i);
    expect(p.tags).toContain("Proyecto: omi");
  });

  it("procedural: quote humaniza la key, sin sesión, avisa si está stale", () => {
    const p = presentDetail("procedural", procedural);
    expect(p.quote).toBe("Foco horario");
    expect(p.fromSession).toBe(false);
    expect(p.note).toBeDefined();
    expect(p.meta).toContainEqual({ label: "Confianza", value: "86%" });
  });
});

describe("sessionRefOf", () => {
  it("resuelve la sesión por capa", () => {
    expect(sessionRefOf("semantic", semantic)).toBe(SESSION);
    expect(sessionRefOf("episodic", episodic)).toBe(SESSION);
    expect(sessionRefOf("procedural", procedural)).toBeNull();
  });
});

describe("relatedEntries", () => {
  const list: MemoryList = {
    semantic: { items: [semantic], total: 1 },
    episodic: { items: [episodic], total: 1 },
    procedural: { items: [procedural], total: 1 },
  };

  it("trae hermanos de la misma sesión, excluyendo el actual", () => {
    const related = relatedEntries(list, {
      sessionId: SESSION,
      excludeLayer: "semantic",
      excludeRef: UUID,
    });
    // El semántico (actual) queda excluido; el episódico de la misma sesión entra.
    expect(related).toHaveLength(1);
    expect(related[0]?.layer).toBe("episodic");
  });

  it("sin sesión (null) no hay relacionados", () => {
    expect(
      relatedEntries(list, {
        sessionId: null,
        excludeLayer: "procedural",
        excludeRef: "foco_horario",
      }),
    ).toEqual([]);
  });
});
