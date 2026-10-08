// Pruebas de interfaz de Proyecciones, Impuestos y Deudas con respuestas reales de la API (ver backend/scripts/exportar_fixtures_front.py).
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import fixtures from "./fixtures/predictivo.json";

const negocio = { actual: "boutique" as "boutique" | "papeleria" };

vi.mock("../context/Sesion", () => ({
  useSesion: () => ({
    usuario: { id_usuario: 1, nombre: "Prueba", email: "p@example.com" },
    empresas: [{ id_empresa: 3, nombre_negocio: "Prueba", giro: "Ropa", rol: "dueno" }],
    empresa: { id_empresa: 3, tiene_datos: true, ultimo_dato: "2026-09-30", giro: "Ropa", ciudad: null, umbrales: { dias_inventario_bajo: 3 } },
    cargando: false,
  }),
}));

const CLARA = { texto: "Resumen de prueba de Clara.", redactado_por_ia: false, aviso: "Orientación general, no constituye asesoría financiera, contable ni fiscal." };

beforeAll(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.stubGlobal("fetch", vi.fn(async (entrada: string) => {
    const ruta = String(entrada).split("?")[0];
    const datos = fixtures[negocio.actual] as Record<string, unknown>;
    const cuerpo =
      ruta.endsWith("/clara") ? CLARA :
      ruta.endsWith("/proyecciones") ? datos.proyecciones :
      ruta.endsWith("/impuestos/gastos") ? datos.gastos :
      ruta.endsWith("/impuestos") ? datos.impuestos :
      ruta.endsWith("/deudas") ? datos.deudas : {};
    return new Response(JSON.stringify(cuerpo), { status: 200, headers: { "content-type": "application/json" } });
  }));
});

afterEach(() => {
  negocio.actual = "boutique";
});

describe("Proyecciones", () => {
  it("muestra pronóstico, efectivo, inventario y consejos", async () => {
    const { Proyecciones } = await import("../pages/Proyecciones");
    render(<MemoryRouter><Proyecciones /></MemoryRouter>);
    expect(await screen.findByText("Días de colchón")).toBeInTheDocument();
    expect(screen.getByText("Precisión aproximada")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Punto de equilibrio del mes" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Horizonte de las gráficas" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Compras sugeridas de inventario" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Reparto sugerido de la utilidad" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Simulador de escenarios" })).toBeInTheDocument();
    expect(await screen.findByText("Resumen de prueba de Clara.")).toBeInTheDocument();
  });

  it("en el negocio en riesgo avisa que la utilidad no cubre impuestos y deudas", async () => {
    const { Proyecciones } = await import("../pages/Proyecciones");
    render(<MemoryRouter><Proyecciones /></MemoryRouter>);
    expect((await screen.findAllByText(/no alcanza para impuestos y pagos de deuda/i)).length).toBeGreaterThan(0);
  });
});

describe("Impuestos", () => {
  it("muestra lo que se paga, el aviso legal y el clasificador de deducciones", async () => {
    negocio.actual = "papeleria";
    const { Impuestos } = await import("../pages/Impuestos");
    render(<MemoryRouter><Impuestos /></MemoryRouter>);
    expect(await screen.findByText("Pagas al SAT")).toBeInTheDocument();
    expect(screen.getAllByText(/No sustituye la declaración ni la asesoría de un contador/).length).toBeGreaterThan(0);
    expect(screen.getByText(/En RESICO los gastos NO se deducen para ISR/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Gastos deducibles del mes" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Calendario fiscal" })).toBeInTheDocument();
  });

  it("en Actividades Empresariales compara los dos regímenes", async () => {
    const { Impuestos } = await import("../pages/Impuestos");
    render(<MemoryRouter><Impuestos /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: /Comparación de régimen/ })).toBeInTheDocument();
    expect(screen.getByText(/Actividades Empresariales te cuesta/)).toBeInTheDocument();
  });
});

describe("Deudas", () => {
  it("lista las deudas con sus alertas del negocio en riesgo", async () => {
    const { Deudas } = await import("../pages/Deudas");
    render(<MemoryRouter><Deudas /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Tarjeta Santander Negocios" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Préstamo de financiera rápida" })).toBeInTheDocument();
    expect(screen.getByText("Tu utilidad no alcanza para tus deudas")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Orden de pago recomendado" })).toBeInTheDocument();
    const tarjeta = screen.getByRole("heading", { name: "Tarjeta Santander Negocios" }).closest("article") as HTMLElement;
    expect(within(tarjeta).getByText(/Usas 88% de tu límite/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: /Agregar deuda/ })).toBeEnabled());
  });
});
