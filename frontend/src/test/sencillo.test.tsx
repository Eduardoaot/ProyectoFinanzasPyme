import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VentanaClara, type TemaClara } from "../components/sencillo/VentanaClara";
import { partesRespuesta } from "../hooks/useConversacion";

const enviar = vi.fn();
let mensajes: unknown[] = [];

vi.mock("../hooks/useConversacion", async (original) => ({
  ...(await original<typeof import("../hooks/useConversacion")>()),
  useConversacion: () => ({
    mensajes, ocupado: false, enviar, cancelar: vi.fn(), hablando: null, hablar: vi.fn(), callar: vi.fn(),
  }),
}));

vi.mock("../context/Sesion", () => ({ useSesion: () => ({ empresa: { id_empresa: 1 } }) }));
vi.mock("../context/Periodo", () => ({ usePeriodo: () => ({ params: {} }) }));
const stream = vi.fn();
vi.mock("../lib/api", () => ({ api: { stream: (...args: unknown[]) => stream(...args) } }));

const tema: TemaClara = {
  titulo: "Tus impuestos",
  explicacion: ["El SAT es la oficina del gobierno que cobra los impuestos."],
  preguntas: [{ texto: "¿Por qué le tengo que pagar al SAT?", envia: "¿Qué es el SAT?" }, { texto: "¿Qué es el IVA?" }],
};

const respuestaSistema = (answer: string) => ({
  id: "c1", rol: "clara", estado: "listo", texto: "",
  respuesta: { answer, intencion: "impuestos", periodo: {}, fuente: "plantilla", sugerencias: [], datos: {} },
});

describe("ventana de Clara (Inicio sencillo)", () => {
  beforeEach(() => {
    enviar.mockClear();
    stream.mockReset();
    mensajes = [];
  });

  it("explica el tema sin IA y manda la pregunta guía, con la frase que entiende el chat", async () => {
    render(<VentanaClara tema={tema} onCerrar={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: "Tus impuestos" })).toBeInTheDocument();
    expect(screen.getByText(/oficina del gobierno/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "¿Por qué le tengo que pagar al SAT?" }));
    expect(enviar).toHaveBeenCalledWith("¿Qué es el SAT?");
    await userEvent.click(screen.getByRole("button", { name: "¿Qué es el IVA?" }));
    expect(enviar).toHaveBeenLastCalledWith("¿Qué es el IVA?");
  });

  it("permite escribir una pregunta propia y se cierra con Escape", async () => {
    const onCerrar = vi.fn();
    render(<VentanaClara tema={tema} onCerrar={onCerrar} />);
    await userEvent.type(screen.getByLabelText("Escribe tu pregunta"), "¿cuándo pago?");
    await userEvent.click(screen.getByRole("button", { name: "Preguntar" }));
    expect(enviar).toHaveBeenCalledWith("¿cuándo pago?");
    await userEvent.keyboard("{Escape}");
    expect(onCerrar).toHaveBeenCalled();
  });

  it("muestra primero la explicación en palabras y lo que se puede hacer; los números quedan aparte", async () => {
    mensajes = [respuestaSistema(
      "### Impuestos\n\n**Este mes**\n- Pagas $1,858.61\n\n**Lo que significa**\n\nEste mes le pagas al SAT $1,858.61.\n\n**Recomendaciones**\n- Aparta un poco cada semana.",
    )];
    render(<VentanaClara tema={tema} onCerrar={vi.fn()} />);
    expect(screen.getByText("Este mes le pagas al SAT $1,858.61.")).toBeInTheDocument();
    expect(screen.getByText("Aparta un poco cada semana.")).toBeInTheDocument();
    expect(screen.queryByText("Pagas $1,858.61")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Ver los números/ }));
    expect(screen.getByText("Pagas $1,858.61")).toBeInTheDocument();
  });

  it("«otras palabras» pide la versión de la IA aparte y la marca como redactada por IA", async () => {
    mensajes = [
      { id: "u1", rol: "usuario", estado: "listo", texto: "¿Qué es el SAT?" },
      respuestaSistema("### SAT\n\n**Lo que significa**\n\nTe toca pagar $1,858.61."),
    ];
    stream.mockImplementation((_ruta: string, _cuerpo: unknown, alEvento: (e: Record<string, unknown>) => void) => {
      alEvento({ tipo: "final", respuesta: { answer: "**Lo que significa**\n\nEl SAT cobra los impuestos.", fuente: "ollama" } });
      return Promise.resolve();
    });
    render(<VentanaClara tema={tema} onCerrar={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /otras palabras/ }));
    const [ruta, cuerpo] = stream.mock.calls[0];
    expect(ruta).toBe("/empresas/1/chat/stream");
    expect(cuerpo).toMatchObject({ mensaje: "¿Qué es el SAT?", sencillo: true });
    expect(cuerpo).not.toHaveProperty("usar_ia");
    expect(screen.getByText("Redactado por IA")).toBeInTheDocument();
    expect(screen.getByText("El SAT cobra los impuestos.")).toBeInTheDocument();
    expect(screen.getByText("Te toca pagar $1,858.61.")).toBeInTheDocument(); // la del sistema sigue ahí
  });

  it("si la IA falla o inventa cifras, dice que la respuesta del sistema es la correcta", async () => {
    mensajes = [
      { id: "u1", rol: "usuario", estado: "listo", texto: "¿Qué es el SAT?" },
      respuestaSistema("**Lo que significa**\n\nTe toca pagar $1,858.61."),
    ];
    stream.mockImplementation((_r: string, _c: unknown, alEvento: (e: Record<string, unknown>) => void) => {
      alEvento({ tipo: "final", respuesta: { answer: "**Lo que significa**\n\nTe toca pagar $1,858.61.", fuente: "plantilla" } });
      return Promise.resolve();
    });
    render(<VentanaClara tema={tema} onCerrar={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /otras palabras/ }));
    expect(screen.getByText(/La respuesta de arriba es la correcta/)).toBeInTheDocument();
  });
});

describe("partes de una respuesta de Clara", () => {
  it("separa la explicación y las recomendaciones del markdown", () => {
    const r = partesRespuesta("### T\n\n**Lo que significa**\n\nVas bien.\n\n**Recomendaciones**\n- Uno\n- Dos\n\n> _aviso_");
    expect(r).toEqual({ significado: "Vas bien.", recomendaciones: ["Uno", "Dos"] });
  });
});
