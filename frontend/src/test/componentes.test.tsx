import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { TarjetaAlerta } from "../components/AlertaTarjeta";
import { Cambio, Segmentado, Semaforo } from "../components/ui/basicos";
import type { Alerta } from "../lib/tipos";

describe("semáforo", () => {
  it("nunca depende solo del color: lleva texto", () => {
    render(<Semaforo estado="rojo" />);
    expect(screen.getByText("Acción")).toBeInTheDocument();
  });
  it("acepta texto propio", () => {
    render(<Semaforo estado="verde" texto="12 d" />);
    expect(screen.getByText("12 d")).toBeInTheDocument();
  });
});

describe("cambio vs periodo anterior", () => {
  it("una baja de ventas se marca como mala", () => {
    const { container } = render(<Cambio valor={-0.2} />);
    expect(container.querySelector(".baja")).not.toBeNull();
  });
  it("en gastos, bajar es bueno (invertido)", () => {
    const { container } = render(<Cambio valor={-0.2} invertido />);
    expect(container.querySelector(".sube")).not.toBeNull();
  });
});

describe("control segmentado", () => {
  it("avisa el valor elegido", async () => {
    const onChange = vi.fn();
    render(<Segmentado etiqueta="Periodo" valor="mes" onChange={onChange}
      opciones={[{ valor: "mes", texto: "Mes" }, { valor: "anio", texto: "Año" }]} />);
    expect(screen.getByRole("button", { name: "Mes" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Año" }));
    expect(onChange).toHaveBeenCalledWith("anio");
  });
});

describe("tarjeta de alerta", () => {
  const alerta: Alerta = {
    id: "flujo_negativo", codigo: "flujo_negativo", nivel: "rojo", modulo: "flujo",
    titulo: "Tu efectivo podría no alcanzar en 30 días", mensaje: "En 30 días tendrías -$4,082.99.",
    accion: "Pospón compras que no sean urgentes.", metricas: {}, redactado_por_ia: true,
  };
  it("muestra título, mensaje, acción, nivel y enlace al módulo", () => {
    render(<MemoryRouter><TarjetaAlerta alerta={alerta} /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: alerta.titulo })).toBeInTheDocument();
    expect(screen.getByText(alerta.mensaje)).toBeInTheDocument();
    expect(screen.getByText(alerta.accion)).toBeInTheDocument();
    expect(screen.getByText("Acción")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ver detalle/ })).toHaveAttribute("href", "/flujo");
  });
});
