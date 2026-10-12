import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { TarjetaAlerta } from "../components/AlertaTarjeta";
import { KpiCard } from "../components/ui/KpiCard";
import type { Alerta, Inicio } from "../lib/tipos";

const inicio: Inicio = {
  tiene_datos: true,
  como_te_fue: { mes: "septiembre", ventas: 17650, te_quedo: 6933, gastaste: 10717, cambio_ventas: -0.12, estado: "amarillo",
    frase: "En septiembre sí te quedaron $6,933, pero vendiste menos que el mes anterior." },
  ventas_por_mes: [{ etiqueta: "Ago", ventas: 20000, actual: false }, { etiqueta: "Sep", ventas: 17650, actual: true }],
  productos: [{
    nombre: "Cuaderno profesional", unidad: "pieza", vendiste: 40, te_dejo: 900, inventario: "rojo", precio: 45, costo: 22.5,
    te_quedan: 3, dias_te_alcanzan: 2, pide: 25, consejo: "Se te acaba: pide unas 25 piezas para 2 semanas.", consejo_estado: "rojo",
  }],
  lo_que_viene: null, impuestos: null, deudas: null,
};

vi.mock("../context/Sesion", () => ({
  useSesion: () => ({
    usuario: { nombre: "Ana López" }, empresa: { id_empresa: 1, tiene_datos: true },
    empresas: [{ id_empresa: 1, rol: "dueno" }],
  }),
}));
vi.mock("../hooks/useApi", () => ({ useApi: () => ({ datos: inicio, error: null, cargando: false }) }));

describe("Inicio sencillo interactivo", () => {
  it("la tarjeta muestra solo lo esencial y la frase completa sale al picarla", async () => {
    const { InicioSencillo } = await import("../pages/InicioSencillo");
    render(<MemoryRouter><InicioSencillo /></MemoryRouter>);
    expect(screen.queryByText(/vendiste menos que el mes anterior/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Ver detalle: ¿Cómo te fue en septiembre?" }));
    expect(screen.getByRole("dialog", { name: "¿Cómo te fue en septiembre?" })).toBeInTheDocument();
    expect(screen.getByText(/vendiste menos que el mes anterior/)).toBeInTheDocument();
  });

  it("picar un producto abre su mini resumen con el consejo calculado por el sistema", async () => {
    const { InicioSencillo } = await import("../pages/InicioSencillo");
    render(<MemoryRouter><InicioSencillo /></MemoryRouter>);
    await userEvent.click(screen.getByRole("row", { name: "Cuaderno profesional: ver resumen" }));
    const ventana = screen.getByRole("dialog", { name: "Cuaderno profesional" });
    expect(ventana).toHaveTextContent("Lo vendes en$45");
    expect(ventana).toHaveTextContent("$22.50");
    expect(ventana).toHaveTextContent("Se te acaba: pide unas 25 piezas para 2 semanas.");
    expect(within(ventana).getByRole("link", { name: "Ir a la sección" })).toHaveAttribute("href", "/productos");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});

describe("detalles del modo avanzado", () => {
  it("una tarjeta KPI abre su detalle con la explicación del término", async () => {
    render(<KpiCard etiqueta="Margen" tecnico="Margen = utilidad / ventas" valor={38.2} formato={(n) => `${n.toFixed(1)}%`}
      serie={[{ etiqueta: "Ago", valor: 30 }, { etiqueta: "Sep", valor: 38.2 }]} />);
    await userEvent.click(screen.getByRole("button", { name: "Ver detalle de Margen" }));
    const ventana = screen.getByRole("dialog", { name: "Margen" });
    expect(ventana).toHaveTextContent("Margen = utilidad / ventas");
    expect(ventana).toHaveTextContent("Más alto (Sep)");
  });

  it("una alerta se abre en detalle con sus cifras en palabras sencillas", async () => {
    const alerta: Alerta = {
      id: "margen", codigo: "margen_bajo", nivel: "rojo", modulo: "finanzas", titulo: "Tu margen está bajo",
      mensaje: "Tu margen bajó a 18%.", accion: "Revisa tus precios.", metricas: { margen: "18.0%", de_cada_100: "$18" },
      redactado_por_ia: false,
    };
    render(<MemoryRouter><TarjetaAlerta alerta={alerta} compacta /></MemoryRouter>);
    await userEvent.click(screen.getByText(alerta.mensaje));
    const ventana = screen.getByRole("dialog", { name: alerta.titulo });
    expect(ventana).toHaveTextContent("De cada $100 te quedan");
    expect(ventana).toHaveTextContent("Revisa tus precios.");
  });
});
