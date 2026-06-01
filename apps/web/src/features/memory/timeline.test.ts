import type { MemoryList } from "@ynara/shared-schemas";
import { describe, expect, it } from "vitest";
import {
  entriesForLayer,
  formatEntryDate,
  groupByBucket,
  humanizeKey,
  toTimelineEntries,
} from "./timeline";

const UUID = "0193aaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const NOW = new Date("2026-06-01T12:00:00Z");

function iso(daysAgo: number, hoursAgo = 0): string {
  return new Date(NOW.getTime() - daysAgo * 86_400_000 - hoursAgo * 3_600_000).toISOString();
}

const list: MemoryList = {
  semantic: {
    items: [
      {
        id: `${UUID}1`.slice(0, 36),
        user_id: UUID,
        content: "Hecho reciente",
        importance: 50,
        source_session_id: null,
        created_at: iso(0, 2), // hoy
        updated_at: iso(0, 2),
      },
    ],
    total: 1,
  },
  episodic: {
    items: [
      {
        id: UUID,
        user_id: UUID,
        session_id: UUID,
        summary: "Momento de hace 3 días",
        is_sensitive: false,
        retention_days: 365,
        occurred_at: iso(3),
        topics: {},
        created_at: iso(3),
        updated_at: iso(3),
      },
    ],
    total: 1,
  },
  procedural: {
    items: [
      {
        id: UUID,
        user_id: UUID,
        key: "foco_horario",
        value: { preferencia: "mañana" },
        confidence: 0.8,
        last_reinforced_at: iso(40), // hace tiempo
        stale: false,
        created_at: iso(60),
        updated_at: iso(40),
      },
    ],
    total: 1,
  },
};

describe("humanizeKey", () => {
  it("convierte una key técnica en título legible", () => {
    expect(humanizeKey("foco_horario")).toBe("Foco horario");
    expect(humanizeKey("tono-cliente-omi")).toBe("Tono cliente omi");
  });

  it("no rompe con una key vacía o sin separadores", () => {
    expect(humanizeKey("")).toBe("");
    expect(humanizeKey("foco")).toBe("Foco");
  });
});

describe("toTimelineEntries", () => {
  it("aplana las 3 capas y ordena por fecha desc", () => {
    const entries = toTimelineEntries(list);
    expect(entries).toHaveLength(3);
    // El hecho de hoy va primero; la costumbre de hace 40 días, última.
    expect(entries[0]?.title).toBe("Hecho reciente");
    expect(entries[0]?.layer).toBe("semantic");
    expect(entries[2]?.layer).toBe("procedural");
  });

  it("usa la fecha canónica correcta por capa", () => {
    const entries = toTimelineEntries(list);
    const procedural = entries.find((e) => e.layer === "procedural");
    // procedural.ref es la key, no el UUID.
    expect(procedural?.ref).toBe("foco_horario");
    expect(procedural?.title).toBe("Foco horario");
  });
});

describe("entriesForLayer", () => {
  it("normaliza una sola capa y ordena desc", () => {
    const entries = entriesForLayer("semantic", list.semantic.items);
    expect(entries).toHaveLength(1);
    expect(entries[0]?.layer).toBe("semantic");
  });
});

describe("groupByBucket", () => {
  it("agrupa en buckets relativos y saltea los vacíos", () => {
    const groups = groupByBucket(toTimelineEntries(list), NOW);
    const labels = groups.map((g) => g.bucket);
    expect(labels).toContain("Hoy");
    expect(labels).toContain("Esta semana");
    expect(labels).toContain("Hace tiempo");
    // No hay nada en "Este mes" (el de 40 días cae en "Hace tiempo").
    expect(labels).not.toContain("Este mes");
  });

  it("mantiene el orden canónico de buckets", () => {
    const groups = groupByBucket(toTimelineEntries(list), NOW);
    expect(groups[0]?.bucket).toBe("Hoy");
  });
});

describe("formatEntryDate", () => {
  it("formatea relativo a now", () => {
    expect(formatEntryDate(iso(0, 2), NOW)).toMatch(/^hoy \d{2}:\d{2}$/);
    expect(formatEntryDate(iso(1), NOW)).toBe("ayer");
    expect(formatEntryDate(iso(3), NOW)).toBe("hace 3 días");
  });

  it("usa fecha corta para lo más viejo que una semana", () => {
    // 40 días atrás desde el 1 jun 2026 → ~22 abr.
    expect(formatEntryDate(iso(40), NOW)).toMatch(/^\d{1,2} [a-z]{3}$/);
  });
});
