import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { TarjetaAlerta } from "../components/AlertaTarjeta";
import { MenuUsuario } from "../components/layout/MenuUsuario";
import { SelectorEmpresa } from "../components/layout/SelectorEmpresa";
import { Cambio, Segmentado, Semaforo } from "../components/ui/basicos";
import type { Alerta, EmpresaResumen } from "../lib/tipos";

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

describe("selector de negocio", () => {
  const empresas: EmpresaResumen[] = [
    { id_empresa: 1, nombre_negocio: "Papelería El Lápiz Feliz", giro: "Papelería", ciudad: "CDMX", rol: "consulta" },
    { id_empresa: 2, nombre_negocio: "Boutique Brisa", giro: "Ropa y accesorios", ciudad: null, rol: "dueno" },
  ];
  it("con un solo negocio muestra el nombre, sin menú", () => {
    render(<SelectorEmpresa empresas={[empresas[1]]} idActual={2} nombre="Boutique Brisa" onCambiar={vi.fn()} />);
    expect(screen.getByText("Boutique Brisa")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByText("Solo puedes ver")).toBeNull();
  });
  it("con varios negocios abre un menú, marca el rol y cambia de negocio", async () => {
    const onCambiar = vi.fn();
    render(<SelectorEmpresa empresas={empresas} idActual={1} nombre="Papelería El Lápiz Feliz" onCambiar={onCambiar} />);
    expect(screen.getByText("Solo puedes ver")).toBeInTheDocument();
    const boton = screen.getByRole("button", { name: /Cambiar de negocio/ });
    await userEvent.click(boton);
    expect(boton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/Eres dueño/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Boutique Brisa/ }));
    expect(onCambiar).toHaveBeenCalledWith(2);
  });
});

describe("menú de la cuenta", () => {
  it("muestra nombre y correo, lleva al perfil y cierra sesión", async () => {
    const onSalir = vi.fn();
    render(
      <MemoryRouter>
        <MenuUsuario usuario={{ id_usuario: 1, nombre: "Ana Ruiz", email: "ana.ruiz@example.com" }} onSalir={onSalir} />
      </MemoryRouter>,
    );
    expect(screen.queryByText("ana.ruiz@example.com")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Tu cuenta: Ana Ruiz/ }));
    expect(screen.getByText("ana.ruiz@example.com")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Mi perfil/ })).toHaveAttribute("href", "/perfil");
    await userEvent.click(screen.getByRole("button", { name: /Cerrar sesión/ }));
    expect(onSalir).toHaveBeenCalled();
  });
});
