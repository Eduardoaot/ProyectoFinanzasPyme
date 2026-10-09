import { useCallback, useEffect, useRef, useState } from "react";
import { usePeriodo } from "../context/Periodo";
import { useSesion } from "../context/Sesion";
import { api } from "../lib/api";
import { textoParaVoz } from "../lib/formato";
import type { ChatRespuesta } from "../lib/tipos";
import { useSintesis } from "../lib/voz";

export interface Mensaje {
  id: string;
  rol: "usuario" | "clara";
  texto: string;
  base?: string;
  narrativa?: string;
  estado: "pensando" | "escribiendo" | "listo" | "error" | "interrumpido";
  respuesta?: ChatRespuesta;
}

let contador = 0;
const nuevoId = () => `m${Date.now()}-${(contador += 1)}`;

/** Texto que queda cuando el usuario interrumpe: lo que alcanzó a escribirse y "..." al final. */
export function textoInterrumpido(m: Mensaje): string {
  if (!m.base) return "...";
  const narrativa = m.narrativa?.trim();
  return narrativa ? `${m.base}\n\n**Lo que significa**\n\n${narrativa}...` : `${m.base}\n\n...`;
}

/** Partes de una respuesta de Clara: la explicación en palabras y las recomendaciones. */
export function partesRespuesta(answer: string): { significado: string; recomendaciones: string[] } {
  const significado = answer.match(/\*\*Lo que significa\*\*\n+([\s\S]+?)(\n\n|$)/)?.[1]?.trim() ?? "";
  const bloque = answer.match(/\*\*Recomendaciones\*\*\n((?:- .+\n?)+)/)?.[1] ?? "";
  const recomendaciones = bloque.split("\n").map((l) => l.replace(/^- /, "").trim()).filter(Boolean);
  return { significado, recomendaciones };
}

/** Qué se lee en voz alta: respuestas cortas completas; en las largas, el título y la interpretación. */
export function textoALeer(r: ChatRespuesta): string {
  if (r.answer.length < 650) return textoParaVoz(r.answer);
  const titulo = r.answer.match(/^###\s*(.+)$/m)?.[1] ?? "";
  const { significado, recomendaciones } = partesRespuesta(r.answer);
  const recomendacion = recomendaciones[0] ?? "";
  return textoParaVoz([titulo, significado, recomendacion && `Te recomiendo: ${recomendacion}`].filter(Boolean).join(". "));
}

/**
 * Una conversación con Clara. El chat flotante tiene una; cada ventana de "¿Qué es esto?" del
 * Inicio sencillo abre otra, aparte, en modo sencillo (palabras de todos los días, sin jerga).
 */
export function useConversacion({ sencillo = false, usarIa = true, vozInicial = true }: {
  sencillo?: boolean;
  /** false: responde el sistema al instante; la redacción de la IA se pide aparte. */
  usarIa?: boolean;
  vozInicial?: boolean;
} = {}) {
  const { empresa } = useSesion();
  const { params } = usePeriodo();
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [vozAutomatica, setVozAutomaticaEstado] = useState(vozInicial);
  const control = useRef<AbortController | null>(null);
  const enCurso = useRef<string | null>(null);
  const ultimaIntencion = useRef<string | null>(null);
  const { hablando, hablar, callar } = useSintesis();

  // Cada negocio tiene su propia conversación.
  useEffect(() => {
    control.current?.abort();
    enCurso.current = null;
    setMensajes([]);
    ultimaIntencion.current = null;
  }, [empresa?.id_empresa]);

  // Al cerrar la ventana no se queda una respuesta corriendo.
  useEffect(() => () => control.current?.abort(), []);

  const actualizar = useCallback((id: string, cambios: Partial<Mensaje>) => {
    setMensajes((ms) => ms.map((m) => (m.id === id ? { ...m, ...cambios } : m)));
  }, []);

  /** Detiene la respuesta en curso sin borrarla: se conserva lo escrito y termina en "...". */
  const interrumpir = useCallback(() => {
    control.current?.abort();
    control.current = null;
    const id = enCurso.current;
    enCurso.current = null;
    if (!id) return;
    setMensajes((ms) =>
      ms.map((m) =>
        m.id === id && (m.estado === "pensando" || m.estado === "escribiendo")
          ? { ...m, texto: textoInterrumpido(m), estado: "interrumpido", narrativa: undefined }
          : m,
      ),
    );
  }, []);

  const enviar = useCallback(
    (texto: string) => {
      const limpio = texto.trim();
      if (!limpio || !empresa) return;
      interrumpir();
      callar();
      const ctrl = new AbortController();
      control.current = ctrl;
      const idClara = nuevoId();
      enCurso.current = idClara;
      setMensajes((ms) => [
        ...ms,
        { id: nuevoId(), rol: "usuario", texto: limpio, estado: "listo" },
        { id: idClara, rol: "clara", texto: "", estado: "pensando" },
      ]);
      setOcupado(true);
      let narrativa = "";
      api
        .stream(
          `/empresas/${empresa.id_empresa}/chat/stream`,
          { mensaje: limpio, ...params, intencion_anterior: ultimaIntencion.current, ...(sencillo ? { sencillo: true } : {}), ...(usarIa ? {} : { usar_ia: false }) },
          (evento) => {
            if (evento.tipo === "inicio") {
              actualizar(idClara, { base: String(evento.base), estado: "escribiendo" });
            } else if (evento.tipo === "token") {
              narrativa += String(evento.texto);
              actualizar(idClara, { narrativa });
            } else if (evento.tipo === "final") {
              const r = evento.respuesta as ChatRespuesta;
              ultimaIntencion.current = r.intencion;
              if (enCurso.current === idClara) enCurso.current = null;
              actualizar(idClara, { texto: r.answer, estado: "listo", respuesta: r, narrativa: undefined });
              if (vozAutomatica) hablar(textoALeer(r), idClara);
            }
          },
          ctrl.signal,
        )
        .catch((e: Error) => {
          if (e.name === "AbortError") return;
          if (enCurso.current === idClara) enCurso.current = null;
          actualizar(idClara, { texto: e.message, estado: "error" });
        })
        .finally(() => {
          if (control.current === ctrl) setOcupado(false);
        });
    },
    [empresa, params, sencillo, usarIa, actualizar, callar, hablar, vozAutomatica, interrumpir],
  );

  const cancelar = useCallback(() => {
    interrumpir();
    setOcupado(false);
  }, [interrumpir]);

  const limpiar = useCallback(() => setMensajes([]), []);
  const setVozAutomatica = useCallback((v: boolean) => {
    if (!v) callar();
    setVozAutomaticaEstado(v);
  }, [callar]);
  const leer = useCallback((m: Mensaje) => m.respuesta && hablar(textoALeer(m.respuesta), m.id), [hablar]);

  return { mensajes, ocupado, enviar, cancelar, limpiar, vozAutomatica, setVozAutomatica, hablando, hablar, leer, callar };
}
