import { describe, expect, it } from "vitest";

import {
  EpisodicMemoryOutSchema,
  MemoryExportSchema,
  MemoryListSchema,
  MemorySearchResponseSchema,
  MemoryWipeConfirmSchema,
  MemoryWipeConflictSchema,
  MemoryWipePreviewSchema,
  MemoryWipeResultSchema,
  memoryOutSchemaFor,
  ProceduralMemoryOutSchema,
  SemanticMemoryOutSchema,
  SemanticMemoryPatchSchema,
} from "./memory";

const ISO = "2026-05-08T09:42:00+00:00";
const UUID = "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const semantic = {
  id: UUID,
  user_id: UUID,
  content: "Decidiste arrancar la tesis por el capítulo 3.",
  importance: 70,
  source_session_id: UUID,
  created_at: ISO,
  updated_at: ISO,
};

const episodic = {
  id: UUID,
  user_id: UUID,
  session_id: UUID,
  summary: "Charla sobre el brief de Õmi.",
  is_sensitive: false,
  retention_days: 365,
  occurred_at: ISO,
  topics: { proyecto: "tesis" },
  created_at: ISO,
  updated_at: ISO,
};

const procedural = {
  id: UUID,
  user_id: UUID,
  key: "foco_horario",
  value: { preferencia: "mañana" },
  confidence: 0.82,
  last_reinforced_at: ISO,
  stale: false,
  created_at: ISO,
  updated_at: ISO,
};

describe("schemas *Out de capa", () => {
  it("aceptan un payload válido por capa", () => {
    expect(SemanticMemoryOutSchema.safeParse(semantic).success).toBe(true);
    expect(EpisodicMemoryOutSchema.safeParse(episodic).success).toBe(true);
    expect(ProceduralMemoryOutSchema.safeParse(procedural).success).toBe(true);
  });

  it("acepta importance null pero rechaza fuera de rango", () => {
    expect(SemanticMemoryOutSchema.safeParse({ ...semantic, importance: null }).success).toBe(true);
    expect(SemanticMemoryOutSchema.safeParse({ ...semantic, importance: 101 }).success).toBe(false);
  });

  it("rechaza fechas no-ISO", () => {
    expect(SemanticMemoryOutSchema.safeParse({ ...semantic, created_at: "ayer" }).success).toBe(
      false,
    );
  });
});

describe("memoryOutSchemaFor", () => {
  it("devuelve el schema correcto por capa", () => {
    expect(memoryOutSchemaFor("semantic").safeParse(semantic).success).toBe(true);
    expect(memoryOutSchemaFor("episodic").safeParse(episodic).success).toBe(true);
    expect(memoryOutSchemaFor("procedural").safeParse(procedural).success).toBe(true);
    // Una capa no matchea el payload de otra.
    expect(memoryOutSchemaFor("semantic").safeParse(procedural).success).toBe(false);
  });
});

describe("MemoryListSchema", () => {
  it("acepta las 3 capas agrupadas con total", () => {
    const parsed = MemoryListSchema.safeParse({
      semantic: { items: [semantic], total: 1 },
      episodic: { items: [], total: 0 },
      procedural: { items: [procedural], total: 1 },
    });
    expect(parsed.success).toBe(true);
  });

  it("rechaza una rama sin total", () => {
    expect(
      MemoryListSchema.safeParse({
        semantic: { items: [semantic] },
        episodic: { items: [], total: 0 },
        procedural: { items: [], total: 0 },
      }).success,
    ).toBe(false);
  });
});

describe("SemanticMemoryPatchSchema", () => {
  it("acepta content dentro de rango", () => {
    expect(SemanticMemoryPatchSchema.safeParse({ content: "nuevo texto" }).success).toBe(true);
  });

  it("rechaza content vacío o demasiado largo", () => {
    expect(SemanticMemoryPatchSchema.safeParse({ content: "" }).success).toBe(false);
    expect(SemanticMemoryPatchSchema.safeParse({ content: "a".repeat(4097) }).success).toBe(false);
  });
});

describe("MemorySearchResponseSchema", () => {
  it("acepta una respuesta con hits rankeados", () => {
    const parsed = MemorySearchResponseSchema.safeParse({
      query: "brief",
      total: 1,
      results: [
        {
          layer: "episodic",
          ref: UUID,
          snippet: "Charla sobre el brief.",
          score: 0.91,
          occurred_at: ISO,
        },
      ],
    });
    expect(parsed.success).toBe(true);
  });

  it("rechaza score fuera de 0..1", () => {
    expect(
      MemorySearchResponseSchema.safeParse({
        query: "x",
        total: 1,
        results: [{ layer: "semantic", ref: UUID, snippet: "x", score: 1.5, occurred_at: null }],
      }).success,
    ).toBe(false);
  });
});

describe("MemoryExportSchema", () => {
  it("acepta un export versionado de las 3 capas", () => {
    const parsed = MemoryExportSchema.parse({
      version: 1,
      exported_at: ISO,
      semantic: [semantic],
      episodic: [episodic],
      procedural: [procedural],
    });
    expect(parsed.version).toBe(1);
    expect(parsed.semantic).toHaveLength(1);
  });

  it("rechaza version distinta de 1", () => {
    expect(
      MemoryExportSchema.safeParse({
        version: 2,
        exported_at: ISO,
        semantic: [],
        episodic: [],
        procedural: [],
      }).success,
    ).toBe(false);
  });
});

describe("Memory wipe", () => {
  const counts = { semantic: 3, episodic: 1, procedural: 0, total: 4 };

  it("preview y result aceptan conteos + total", () => {
    expect(MemoryWipePreviewSchema.parse(counts)).toEqual(counts);
    expect(MemoryWipeResultSchema.parse(counts)).toEqual(counts);
  });

  it("rechaza conteos negativos", () => {
    expect(
      MemoryWipePreviewSchema.safeParse({ semantic: -1, episodic: 0, procedural: 0, total: 0 })
        .success,
    ).toBe(false);
  });

  it("confirm exige los 3 expected_*", () => {
    expect(
      MemoryWipeConfirmSchema.parse({
        expected_semantic: 3,
        expected_episodic: 1,
        expected_procedural: 0,
      }),
    ).toEqual({ expected_semantic: 3, expected_episodic: 1, expected_procedural: 0 });
    expect(MemoryWipeConfirmSchema.safeParse({ expected_semantic: 3 }).success).toBe(false);
  });

  it("conflict trae message + conteos actuales", () => {
    const conflict = {
      message: "los conteos cambiaron",
      semantic: 5,
      episodic: 2,
      procedural: 1,
      total: 8,
    };
    expect(MemoryWipeConflictSchema.parse(conflict)).toEqual(conflict);
  });
});
