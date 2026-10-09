import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Loader2, Mic, Send, Sparkles, Square, Volume2, VolumeX, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { usePeriodo } from "../../context/Periodo";
import { useSesion } from "../../context/Sesion";
import { partesRespuesta, useConversacion, type Mensaje } from "../../hooks/useConversacion";
import { api } from "../../lib/api";
import { textoParaVoz } from "../../lib/formato";
import type { ChatRespuesta } from "../../lib/tipos";
import { useReconocimiento, vozSoportada } from "../../lib/voz";

export interface PreguntaGuia {
  /** Lo que ve la persona en el botón. */
  texto: string;
  /** Lo que se le manda a Clara, si conviene decirlo de otra forma para que entienda el tema. */
  envia?: string;
}

export interface TemaClara {
  titulo: string;
  /** "¿Qué es esto?": escrito por personas, sin IA, para que salga al instante y sin errores. */
  explicacion: string[];
  preguntas: PreguntaGuia[];
}

interface OtrasPalabras {
  estado: "pensando" | "listo" | "sin_ia";
  texto: string;
}

/**
 * "Explícamelo con otras palabras": la misma pregunta, ahora redactada por la IA en modo sencillo.
 * La respuesta del sistema sigue arriba; esta es un apoyo y se marca como redactada por IA.
 */
function useOtrasPalabras() {
  const { empresa } = useSesion();
  const { params } = usePeriodo();
  const [otras, setOtras] = useState<Record<string, OtrasPalabras>>({});
  const controles = useRef<AbortController[]>([]);
  useEffect(() => () => controles.current.forEach((c) => c.abort()), []);

  const pedir = (id: string, pregunta: string) => {
    if (!empresa) return;
    const ctrl = new AbortController();
    controles.current.push(ctrl);
    let texto = "";
    const poner = (o: OtrasPalabras) => setOtras((prev) => ({ ...prev, [id]: o }));
    poner({ estado: "pensando", texto: "" });
    api.stream(`/empresas/${empresa.id_empresa}/chat/stream`, { mensaje: pregunta, ...params, sencillo: true }, (evento) => {
      if (evento.tipo === "token") {
        texto += String(evento.texto);
        poner({ estado: "pensando", texto });
      } else if (evento.tipo === "final") {
        const r = evento.respuesta as ChatRespuesta;
        const { significado } = partesRespuesta(r.answer);
        // "plantilla" = la IA no respondió o la guardia descartó su texto por traer cifras inventadas.
        poner(r.fuente === "ollama" && significado ? { estado: "listo", texto: significado } : { estado: "sin_ia", texto: "" });
      }
    }, ctrl.signal).catch((e: Error) => {
      if (e.name !== "AbortError") poner({ estado: "sin_ia", texto: "" });
    });
  };
  return { otras, pedir };
}

function RespuestaClara({ m, hablando, onLeer, onCallar, otras, onOtras }: {
  m: Mensaje; hablando: boolean; onLeer: (texto: string) => void; onCallar: () => void;
  otras?: OtrasPalabras; onOtras: () => void;
}) {
  const [verNumeros, setVerNumeros] = useState(false);
  if (m.estado === "pensando") {
    return <p className="clara-pensando"><Loader2 size={20} className="girando" aria-hidden="true" /> Clara está pensando…</p>;
  }
  if (m.estado === "error") return <p className="respuesta-sencilla error">{m.texto}</p>;
  if (m.estado === "escribiendo") {
    return <p className="respuesta-sencilla">{m.narrativa || "Clara está escribiendo…"}</p>;
  }
  const answer = m.respuesta?.answer ?? m.texto;
  const { significado, recomendaciones } = partesRespuesta(answer);
  const numeros = answer.split("**Lo que significa**")[0].trim();
  const texto = significado || textoParaVoz(numeros);
  const paraLeer = [texto, recomendaciones[0] && `Lo que puedes hacer: ${recomendaciones[0]}`].filter(Boolean).join(". ");
  return (
    <div className="pila" style={{ gap: 12 }}>
      <p className="respuesta-sencilla">{texto}</p>
      {recomendaciones.length > 0 && (
        <div className="que-hacer">
          <strong>Lo que puedes hacer:</strong>
          <ul>{recomendaciones.slice(0, 2).map((r) => <li key={r}>{r}</li>)}</ul>
        </div>
      )}
      <div className="fila envolver" style={{ gap: 8 }}>
        {vozSoportada.hablar && (
          <button type="button" className="btn grande" onClick={() => (hablando ? onCallar() : onLeer(paraLeer))}>
            {hablando ? <VolumeX size={20} /> : <Volume2 size={20} />} {hablando ? "Callar" : "Escuchar"}
          </button>
        )}
        {significado && numeros && (
          <button type="button" className="btn grande fantasma" aria-expanded={verNumeros} onClick={() => setVerNumeros((v) => !v)}>
            <ChevronDown size={18} className={verNumeros ? "girada" : ""} /> {verNumeros ? "Ocultar los números" : "Ver los números"}
          </button>
        )}
      </div>
      {verNumeros && <div className="markdown numeros-sencillos"><ReactMarkdown remarkPlugins={[remarkGfm]}>{numeros}</ReactMarkdown></div>}
      {!otras ? (
        <button type="button" className="btn grande fantasma otras-palabras-boton" onClick={onOtras}>
          <Sparkles size={20} /> Explícamelo con otras palabras
        </button>
      ) : otras.estado === "sin_ia" ? (
        <p className="muted">Clara no pudo explicarlo de otra forma en este momento. La respuesta de arriba es la correcta.</p>
      ) : (
        <div className="otras-palabras">
          <span className="chip celeste"><Sparkles size={13} aria-hidden="true" /> Redactado por IA</span>
          {otras.estado === "pensando" && !otras.texto ? (
            <p className="clara-pensando"><Loader2 size={20} className="girando" aria-hidden="true" /> Clara lo está pensando… puede tardar unos segundos.</p>
          ) : (
            <p className="respuesta-sencilla">{otras.texto}</p>
          )}
          {otras.estado === "listo" && vozSoportada.hablar && (
            <button type="button" className="btn grande" onClick={() => onLeer(otras.texto)}>
              <Volume2 size={20} /> Escuchar
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Ventana de Clara del Inicio sencillo: explicación fija + preguntas ya hechas + campo para preguntar. */
export function VentanaClara({ tema, onCerrar }: { tema: TemaClara; onCerrar: () => void }) {
  // Primero responde el sistema (al instante y siempre correcto); la IA se pide con "otras palabras".
  const { mensajes, ocupado, enviar, cancelar, hablando, hablar, callar } = useConversacion({ sencillo: true, usarIa: false, vozInicial: false });
  const { otras, pedir } = useOtrasPalabras();
  const [texto, setTexto] = useState("");
  const cerrar = useRef<HTMLButtonElement>(null);
  const final = useRef<HTMLDivElement>(null);
  const voz = useReconocimiento((dicho) => enviar(dicho));
  const hechas = new Set(mensajes.filter((m) => m.rol === "usuario").map((m) => m.texto));

  // Solo al abrir: si se repitiera en cada render, el foco saltaría a "Cerrar" mientras la persona escribe.
  const alCerrar = useRef({ onCerrar, callar });
  alCerrar.current = { onCerrar, callar };
  useEffect(() => {
    cerrar.current?.focus();
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && alCerrar.current.onCerrar();
    document.addEventListener("keydown", tecla);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tecla);
      document.body.style.overflow = "";
      alCerrar.current.callar();
    };
  }, []);

  useEffect(() => {
    final.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [mensajes]);

  const mandar = (e: FormEvent) => {
    e.preventDefault();
    if (!texto.trim()) return;
    enviar(texto);
    setTexto("");
  };

  return (
    <motion.div className="velo-clara" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onCerrar}>
      <motion.section className="ventana-clara" role="dialog" aria-modal="true" aria-labelledby="ventana-clara-titulo"
        initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 30 }}
        transition={{ type: "spring", stiffness: 320, damping: 32 }} onClick={(e) => e.stopPropagation()}>
        <header className="ventana-clara-cabecera">
          <span className="orbe-clara" aria-hidden="true"><Sparkles size={20} /></span>
          <h2 id="ventana-clara-titulo">{tema.titulo}</h2>
          <button ref={cerrar} type="button" className="btn grande fantasma" onClick={onCerrar}>
            <X size={20} /> Cerrar
          </button>
        </header>

        <div className="ventana-clara-cuerpo">
          <div className="que-es">
            <h3>¿Qué es esto?</h3>
            {tema.explicacion.map((p) => <p key={p}>{p}</p>)}
            {vozSoportada.hablar && (
              <button type="button" className="btn grande" onClick={() => (hablando === "explicacion" ? callar() : hablar(tema.explicacion.join(" "), "explicacion"))}>
                {hablando === "explicacion" ? <VolumeX size={20} /> : <Volume2 size={20} />} {hablando === "explicacion" ? "Callar" : "Escuchar"}
              </button>
            )}
          </div>

          <h3>Toca una pregunta y Clara te contesta</h3>
          <div className="preguntas-guia">
            {tema.preguntas.map((p) => (
              <button key={p.texto} type="button" className="pregunta-guia" disabled={ocupado}
                onClick={() => enviar(p.envia ?? p.texto)} aria-pressed={hechas.has(p.envia ?? p.texto)}>
                {p.texto}
              </button>
            ))}
          </div>

          <div className="pila" style={{ gap: 16 }} aria-live="polite">
            <AnimatePresence initial={false}>
              {mensajes.map((m, i) => (
                <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  className={m.rol === "usuario" ? "pregunta-hecha" : "respuesta-clara"}>
                  {m.rol === "usuario" ? (
                    <p><strong>Tú preguntaste:</strong> {tema.preguntas.find((p) => p.envia === m.texto)?.texto ?? m.texto}</p>
                  ) : (
                    <RespuestaClara m={m} hablando={hablando === m.id} onLeer={(t) => hablar(t, m.id)} onCallar={callar}
                      otras={otras[m.id]} onOtras={() => pedir(m.id, mensajes[i - 1]?.texto ?? "")} />
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={final} />
          </div>
        </div>

        <form className="ventana-clara-pie" onSubmit={mandar}>
          <label htmlFor="pregunta-libre" className="sr-only">Escribe tu pregunta</label>
          <input id="pregunta-libre" className="input grande" placeholder={voz.escuchando ? "Te escucho…" : "O escribe tu pregunta aquí"}
            value={voz.escuchando ? voz.parcial : texto} onChange={(e) => setTexto(e.target.value)} maxLength={500} />
          {vozSoportada.escuchar && (
            <button type="button" className={`btn grande ${voz.escuchando ? "primario" : ""}`} onClick={voz.escuchando ? voz.detener : voz.iniciar}
              aria-label={voz.escuchando ? "Dejar de escuchar" : "Hablarle a Clara"}>
              <Mic size={20} /> <span className="solo-ancho">{voz.escuchando ? "Escuchando" : "Hablar"}</span>
            </button>
          )}
          {ocupado && !texto.trim() ? (
            <button type="button" className="btn grande" onClick={cancelar} aria-label="Detener respuesta"><Square size={18} /></button>
          ) : (
            <button className="btn grande primario" disabled={!texto.trim()} aria-label="Preguntar"><Send size={20} /> <span className="solo-ancho">Preguntar</span></button>
          )}
        </form>
        {voz.error && <p className="mini" style={{ margin: "0 20px 8px", color: "var(--bad-ink)" }}>{voz.error}</p>}
        <p className="mini muted ventana-clara-aviso">Clara usa las cifras que calcula el sistema. Es orientación general, no asesoría financiera.</p>
      </motion.section>
    </motion.div>
  );
}
