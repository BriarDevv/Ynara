import { describe, expect, it } from "vitest";
import { AdminAuditPage, EMPTY_AUDIT_FILTERS } from "@/features/audit/schemas";
import { AdminMoatOut } from "@/features/moat/schemas";
import { AdminModesOut } from "@/features/modes/schemas";
import { AdminOverviewOut } from "@/features/overview/schemas";
import { PlaygroundAgentOut, PlaygroundOut } from "@/features/playground/schemas";
import { ConnectivityOut } from "@/features/sharing/schemas";
import { AdminSystemOut } from "@/features/system/schemas";
import { AdminUsersOut } from "@/features/users/schemas";
import { auditPage } from "@/fixtures/audit";
import { connectivityFixture } from "@/fixtures/connectivity";
import { moatFixture } from "@/fixtures/moat";
import { modesFixture } from "@/fixtures/modes";
import { overviewFixture } from "@/fixtures/overview";
import { playgroundAgentEcho, playgroundEcho } from "@/fixtures/playground";
import { systemFixture } from "@/fixtures/system";
import { usersFixture } from "@/fixtures/users";
import { RANGE_IDS, type RangeId } from "@/stores/range";

/**
 * Test de CONTRATO (blueprint §6 paso 8): cada fixture de `/v1/admin/*` debe
 * parsear limpio contra su Zod. Es la garantía viva de que los datos de demo y
 * el contrato de API no driftean — si un fixture deja de cumplir el shape, el
 * test falla y nombra el endpoint.
 *
 * (Los `*Fixture`/`auditPage` ya hacen `Schema.parse` internamente, así que un
 * fixture roto tira al construirse; acá lo re-parseamos explícito para que el
 * test sea el lugar canónico donde se documenta y verifica el contrato, y para
 * cubrir los 4 rangos de cada vista segmentada por tiempo.)
 */

const RANGES = RANGE_IDS as readonly RangeId[];

describe("contrato fixtures ↔ Zod (blueprint §4)", () => {
  it("overview parsea en todos los rangos", () => {
    for (const range of RANGES) {
      expect(() => AdminOverviewOut.parse(overviewFixture(range))).not.toThrow();
    }
  });

  it("users parsea en todos los rangos", () => {
    for (const range of RANGES) {
      expect(() => AdminUsersOut.parse(usersFixture(range))).not.toThrow();
    }
  });

  it("modes parsea en todos los rangos", () => {
    for (const range of RANGES) {
      expect(() => AdminModesOut.parse(modesFixture(range))).not.toThrow();
    }
  });

  it("moat parsea en todos los rangos", () => {
    for (const range of RANGES) {
      expect(() => AdminMoatOut.parse(moatFixture(range))).not.toThrow();
    }
  });

  it("system parsea (sin rango)", () => {
    expect(() => AdminSystemOut.parse(systemFixture())).not.toThrow();
  });

  it("connectivity parsea (sin rango)", () => {
    expect(() => ConnectivityOut.parse(connectivityFixture())).not.toThrow();
  });

  it("audit page parsea sin filtros y paginada", () => {
    expect(() => AdminAuditPage.parse(auditPage(EMPTY_AUDIT_FILTERS, 50, 0))).not.toThrow();
    expect(() => AdminAuditPage.parse(auditPage(EMPTY_AUDIT_FILTERS, 25, 100))).not.toThrow();
  });

  it("audit page respeta filtros y paginación en memoria", () => {
    const all = auditPage(EMPTY_AUDIT_FILTERS, 1000, 0);
    expect(all.total).toBe(200);
    expect(all.items.length).toBe(200);

    // Filtro por operación: cada fila devuelta matchea, total ≤ total global.
    const writes = auditPage({ ...EMPTY_AUDIT_FILTERS, operation: "write" }, 1000, 0);
    expect(writes.items.every((r) => r.operation === "write")).toBe(true);
    expect(writes.total).toBeLessThanOrEqual(all.total);
    expect(writes.items.length).toBe(writes.total);

    // Filtro por sensible.
    const sensitive = auditPage({ ...EMPTY_AUDIT_FILTERS, sensitive: true }, 1000, 0);
    expect(sensitive.items.every((r) => r.sensitive)).toBe(true);

    // Paginación: limit recorta, offset desplaza.
    const firstPage = auditPage(EMPTY_AUDIT_FILTERS, 50, 0);
    const secondPage = auditPage(EMPTY_AUDIT_FILTERS, 50, 50);
    expect(firstPage.items.length).toBe(50);
    expect(secondPage.items.length).toBe(50);
    expect(firstPage.items[0]?.id).not.toBe(secondPage.items[0]?.id);
  });

  it("audit NUNCA expone record_hash ni target_id (privacidad soberana)", () => {
    const page = auditPage(EMPTY_AUDIT_FILTERS, 1000, 0);
    for (const row of page.items) {
      expect(row).not.toHaveProperty("record_hash");
      expect(row).not.toHaveProperty("target_id");
    }
  });

  // ── Playground (Fase A probe + Fase B agente) ───────────────────────────

  it("playground probe echo parsea contra PlaygroundOut", () => {
    const body = {
      model: "qwen",
      message: "Hola test",
      params: { max_tokens: 256, temperature: 0.7, low_perf: false },
      thinking: null,
    };
    expect(() => PlaygroundOut.parse(playgroundEcho(body))).not.toThrow();
  });

  it("playground probe echo con low_perf y thinking off parsea contra PlaygroundOut", () => {
    const body = {
      model: "gemma4",
      message: "Test low perf",
      params: { max_tokens: 256, temperature: 0.2, low_perf: true },
      thinking: false,
    };
    expect(() => PlaygroundOut.parse(playgroundEcho(body))).not.toThrow();
  });

  it("playground agent echo parsea contra PlaygroundAgentOut", () => {
    const body = {
      model: "qwen",
      message: "Creá un evento para mañana",
      params: { max_tokens: 512, temperature: 0.7, low_perf: false },
      thinking: null,
    };
    const result = playgroundAgentEcho(body);
    expect(() => PlaygroundAgentOut.parse(result)).not.toThrow();
    // Debe tener las 2 tool-calls de ejemplo (calendar + reminder).
    expect(result.actions).toHaveLength(2);
    expect(result.actions[0]?.name).toBe("calendar.create_event");
    expect(result.actions[1]?.name).toBe("reminder.set");
    // Ambas devuelven not_wired (stub, cero efecto real).
    expect(result.actions[0]?.result).toBe("not_wired");
    expect(result.actions[1]?.result).toBe("not_wired");
  });
});
