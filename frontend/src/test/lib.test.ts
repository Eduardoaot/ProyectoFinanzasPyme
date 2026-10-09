import { describe, expect, it } from "vitest";
import { textoALeer, textoInterrumpido } from "../hooks/useConversacion";
import { cambio, dinero, pct, textoParaVoz } from "../lib/formato";
import { rangosPeriodo, rangoAtras, ultimosMeses, ventanasPeriodo } from "../lib/periodos";
import type { ChatRespuesta } from "../lib/tipos";

describe("formato", () => {
  it("formatea pesos mexicanos", () => {
    expect(dinero(170000)).toBe("$170,000");
    expect(dinero(1234.5)).toBe("$1,234.50");
    expect(dinero(null)).toBe("—");
  });
  it("formatea porcentajes y cambios", () => {
    expect(pct(0.3824)).toBe("38.2%");
    expect(cambio(0.123)).toBe("+12.3%");
    expect(cambio(-0.583)).toBe("−58.3%");
    expect(cambio(-60.9)).toBe("−más de 999%");
    expect(cambio(null)).toBe("sin comparación");
  });
  it("prepara texto para la voz", () => {
    const texto = textoParaVoz("### Título\n- **Vendiste:** $17,650\n- Margen: 38.2%\n🔴 Alerta");
    expect(texto).toContain("17,650 pesos");
    expect(texto).toContain("38 punto 2 por ciento");
    expect(texto).not.toMatch(/[#*🔴]/u);
  });
});

describe("periodos", () => {
  it("los rangos del filtro van de 1 mes a 2 años y terminan en el último dato", () => {
    const rangos = rangosPeriodo("2026-09-30");
    expect(rangos.map((r) => r.texto)).toEqual(["1 mes", "2 meses", "3 meses", "6 meses", "1 año", "2 años"]);
    expect(rangos.map((r) => r.clave)).toEqual(["1", "2", "3", "6", "12", "24"]);
    expect(rangos.every((r) => r.hasta === "2026-09-30")).toBe(true);
    expect(rangos[0]).toMatchObject({ desde: "2026-09-01", etiqueta: "último mes" });
    expect(rangos[2]).toMatchObject({ desde: "2026-07-01", etiqueta: "últimos 3 meses" });
    expect(rangos[5]).toMatchObject({ desde: "2024-10-01", etiqueta: "últimos 2 años" });
  });
  it("rangos de la gráfica principal", () => {
    expect(rangoAtras("2026-09-30", 1)).toEqual({ desde: "2026-09-01", hasta: "2026-09-30" });
    expect(rangoAtras("2026-09-30", 3)).toEqual({ desde: "2026-07-01", hasta: "2026-09-30" });
    expect(rangoAtras("2026-09-30", 24)).toEqual({ desde: "2024-10-01", hasta: "2026-09-30" });
    expect(ultimosMeses("2026-09-30", 12, "2024-10-01")).toEqual({ desde: "2025-10-01", hasta: "2026-09-30" });
    expect(ultimosMeses("2024-11-30", 12, "2024-10-01").desde).toBe("2024-10-01");
  });
  it("ventanas de 1 mes: un select por mes, del más reciente al más antiguo", () => {
    const v = ventanasPeriodo("2026-01-01", "2026-09-30", 1);
    expect(v[0]).toMatchObject({ desde: "2026-09-01", hasta: "2026-09-30", etiqueta: "Septiembre 2026" });
    expect(v.at(-1)).toMatchObject({ desde: "2026-01-01", hasta: "2026-01-31" });
    expect(v.map((w) => w.clave)).toEqual(["2026-9", "2026-8", "2026-7", "2026-6", "2026-5", "2026-4", "2026-3", "2026-2", "2026-1"]);
  });
  it("ventanas de 3 meses: rangos de meses de calendario", () => {
    const v = ventanasPeriodo("2026-01-01", "2026-09-30", 3);
    expect(v[0]).toMatchObject({ desde: "2026-07-01", hasta: "2026-09-30", etiqueta: "Julio – Septiembre 2026" });
    expect(v[1]).toMatchObject({ desde: "2026-06-01", hasta: "2026-08-31", etiqueta: "Junio – Agosto 2026" });
    expect(v.at(-1)).toMatchObject({ desde: "2026-01-01", hasta: "2026-03-31", etiqueta: "Enero – Marzo 2026" });
  });
  it("cuando el historial es más corto que el ancho, la primera ventana se recorta", () => {
    const v = ventanasPeriodo("2026-01-01", "2026-09-30", 24);
    expect(v).toHaveLength(1);
    expect(v[0]).toMatchObject({ desde: "2026-01-01", hasta: "2026-09-30", etiqueta: "Enero – Septiembre 2026" });
  });
});

describe("lectura en voz alta", () => {
  const base: Omit<ChatRespuesta, "answer"> = {
    intencion: "analisis_completo",
    periodo: { desde: "2026-01-01", hasta: "2026-09-30", etiqueta: "enero a septiembre 2026" },
    fuente: "ollama",
    sugerencias: [],
    datos: {},
  };
  it("en respuestas largas lee solo título, interpretación y primera recomendación", () => {
    const answer = `### Análisis financiero\n\n**Ingresos**\n${"- Línea con cifras $1,000\n".repeat(40)}\n**Lo que significa**\n\nVas bien este año.\n\n**Recomendaciones**\n- Revisa tus precios.\n- Otra cosa.`;
    const texto = textoALeer({ ...base, answer });
    expect(texto).toContain("Vas bien este año");
    expect(texto).toContain("Revisa tus precios");
    expect(texto).not.toContain("Línea con cifras");
    expect(texto).not.toContain("Otra cosa");
  });
});

describe("interrupción del chat", () => {
  it("si aún no había nada, queda solo '...'", () => {
    expect(textoInterrumpido({ id: "1", rol: "clara", texto: "", estado: "pensando" })).toBe("...");
  });
  it("conserva las cifras y lo que alcanzó a escribir la IA, terminando en '...'", () => {
    const t = textoInterrumpido({ id: "1", rol: "clara", texto: "", estado: "escribiendo", base: "### Ventas", narrativa: "Vas bien este " });
    expect(t).toBe("### Ventas\n\n**Lo que significa**\n\nVas bien este...");
  });
  it("con cifras pero sin texto de la IA, termina en '...'", () => {
    expect(textoInterrumpido({ id: "1", rol: "clara", texto: "", estado: "escribiendo", base: "### Ventas" })).toBe("### Ventas\n\n...");
  });
});
