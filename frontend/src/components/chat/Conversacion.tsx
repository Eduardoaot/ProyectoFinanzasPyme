import { AnimatePresence, motion } from "framer-motion";
import { Copy, Mic, Send, Sparkles, Square, Trash2, Volume2, VolumeX } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useChat, type Mensaje } from "../../context/Chat";
import { useSesion } from "../../context/Sesion";
import { useApi } from "../../hooks/useApi";
import { useReconocimiento, vozSoportada } from "../../lib/voz";

const PREGUNTAS_GUIA = [
  "¿Estoy ganando este mes?",
  "¿Qué producto me deja más?",
  "¿Me va a alcanzar el efectivo?",
  "¿Qué productos van a mejorar su margen?",
  "Hazme un análisis completo",
  "¿Qué significa avalancha y bola de nieve?",
  "¿Dónde gasto demasiado?",
  "¿Qué se me va a agotar?",
];

function OndasVoz() {
  return (
    <span className="ondas-voz" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <motion.i
          key={i}
          animate={{ height: [5, 20, 8, 16, 5] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.12, ease: "easeInOut" }}
        />
      ))}
    </span>
  );
}

function Markdown({ texto }: { texto: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{texto}</ReactMarkdown>
    </div>
  );
}

function BurbujaClara({ m, ultimo }: { m: Mensaje; ultimo: boolean }) {
  const { hablando, leer, callar, enviar } = useChat();
  const [copiado, setCopiado] = useState(false);
  const r = m.respuesta;
  return (
    <div className="msg clara">
      <span className={`orbe-clara ${m.estado !== "listo" || hablando === m.id ? "activa" : ""}`} aria-hidden="true">
        <Sparkles size={16} />
      </span>
      <div className="burbuja-msg" aria-live={ultimo ? "polite" : undefined}>
        {m.estado === "pensando" && (
          <span className="escribiendo" aria-label="Clara está calculando">
            <i />
            <i />
            <i />
          </span>
        )}
        {m.estado === "escribiendo" && (
          <>
            {m.base && <Markdown texto={m.base} />}
            <div className="narrativa-viva">
              <strong className="pequeno">Lo que significa</strong>
              <p className="justificado pequeno" style={{ marginTop: 4 }}>
                {m.narrativa || <span className="muted">Clara está interpretando tus números…</span>}
                <span className="cursor" aria-hidden="true" />
              </p>
            </div>
          </>
        )}
        {(m.estado === "listo" || m.estado === "error" || m.estado === "interrumpido") && <Markdown texto={m.texto} />}
        {r && (
          <div className="msg-pie">
            <span className={`chip ${r.fuente === "ollama" ? "celeste" : ""}`} title="Las cifras siempre las calcula el sistema">
              <Sparkles size={12} />
              {r.fuente === "ollama" ? "Interpretación con IA local" : "Respuesta del sistema"}
            </span>
            <span className="chip">{r.periodo.etiqueta}</span>
            {vozSoportada.hablar && (
              <button
                className="btn chico fantasma"
                onClick={() => (hablando === m.id ? callar() : leer(m))}
                aria-label={hablando === m.id ? "Detener lectura" : "Escuchar respuesta"}
              >
                {hablando === m.id ? <VolumeX size={14} /> : <Volume2 size={14} />}
                {hablando === m.id ? "Detener" : "Escuchar"}
              </button>
            )}
            <button
              className="btn chico fantasma"
              onClick={() => {
                navigator.clipboard?.writeText(JSON.stringify({ answer: r.answer }, null, 2));
                setCopiado(true);
                setTimeout(() => setCopiado(false), 1600);
              }}
              aria-label="Copiar respuesta como JSON"
            >
              <Copy size={14} />
              {copiado ? "¡Copiado!" : "JSON"}
            </button>
          </div>
        )}
        {r && ultimo && r.sugerencias.length > 0 && (
          <div className="fila envolver" style={{ marginTop: 10, gap: 6 }}>
            {r.sugerencias.map((s) => (
              <button key={s} className="chip boton" onClick={() => enviar(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function Conversacion({ compacto = false }: { compacto?: boolean }) {
  const { mensajes, ocupado, enviar, cancelar, limpiar, vozAutomatica, setVozAutomatica } = useChat();
  const { empresa } = useSesion();
  const estadoIA = useApi<{ disponible: boolean; modelo: string; modelo_instalado: boolean }>("/ia/estado");
  const [texto, setTexto] = useState("");
  const lista = useRef<HTMLDivElement>(null);
  const caja = useRef<HTMLTextAreaElement>(null);
  const voz = useReconocimiento((dicho) => {
    setTexto("");
    enviar(dicho);
  });
  const valorCaja = voz.escuchando ? voz.parcial : texto;

  useEffect(() => {
    lista.current?.scrollTo({ top: lista.current.scrollHeight });
  }, [mensajes]);

  // La caja crece con el texto (hasta el max-height del CSS) en lugar de mostrar una barra de desplazamiento.
  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
    el.style.overflowY = el.scrollHeight > el.clientHeight ? "auto" : "hidden";
  }, [valorCaja]);

  const mandar = () => {
    if (!texto.trim()) return;      // si Clara está respondiendo, la nueva pregunta la interrumpe
    enviar(texto);
    setTexto("");
  };
  const alTeclear = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      mandar();
    }
  };
  const ia = estadoIA.datos;

  return (
    <div className="chat">
      <div className="chat-cabecera">
        <span className={`orbe-clara ${ocupado || voz.escuchando ? "activa" : ""}`} aria-hidden="true">
          <Sparkles size={16} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="nombre">Clara · tu asistente financiera</div>
          <div className="estado">
            <span className={`punto-vivo ${ia?.disponible ? "" : "apagado"}`} />
            {ia?.disponible ? `IA local activa (${ia.modelo})` : "IA local apagada: respondo con plantillas"}
          </div>
        </div>
        {vozSoportada.hablar && (
          <button
            className={`btn icono chico ${vozAutomatica ? "celeste" : ""}`}
            onClick={() => setVozAutomatica(!vozAutomatica)}
            aria-pressed={vozAutomatica}
            aria-label={vozAutomatica ? "Desactivar respuestas en voz alta" : "Activar respuestas en voz alta"}
            title="Respuestas en voz alta"
          >
            {vozAutomatica ? <Volume2 size={15} /> : <VolumeX size={15} />}
          </button>
        )}
        {mensajes.length > 0 && (
          <button className="btn icono chico fantasma" onClick={limpiar} aria-label="Borrar conversación" title="Borrar conversación">
            <Trash2 size={15} />
          </button>
        )}
      </div>

      <div className="chat-mensajes" ref={lista}>
        {mensajes.length === 0 && (
          <motion.div className="pila" style={{ alignItems: "center", textAlign: "center", padding: compacto ? "12px 4px" : "28px 8px" }}
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <span className="orbe-clara grande" aria-hidden="true">
              <Sparkles size={28} />
            </span>
            <h3 className="centrado">¡Hola! Soy Clara</h3>
            <p className="muted pequeno justificado" style={{ maxWidth: 380 }}>
              Pregúntame por {empresa?.nombre_negocio ?? "tu negocio"} con tus palabras o con el micrófono. El sistema calcula
              todas las cifras con tus datos; yo te las explico y te digo qué hacer.
            </p>
            <div className="fila envolver" style={{ justifyContent: "center", gap: 8, marginTop: 6 }}>
              {PREGUNTAS_GUIA.slice(0, compacto ? 4 : 8).map((p, i) => (
                <motion.button key={p} className="chip boton" onClick={() => enviar(p)}
                  initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.15 + i * 0.05 }}>
                  {p}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
        <AnimatePresence initial={false}>
          {mensajes.map((m, i) => (
            <motion.div key={m.id} initial={{ opacity: 0, y: 12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: "spring", stiffness: 380, damping: 30 }}>
              {m.rol === "usuario" ? (
                <div className="msg usuario">
                  <div className="burbuja-msg">{m.texto}</div>
                </div>
              ) : (
                <BurbujaClara m={m} ultimo={i === mensajes.length - 1} />
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {(voz.error || voz.escuchando) && (
        <div className="sugerencias" aria-live="polite">
          {voz.escuchando ? (
            <span className="chip celeste">
              <OndasVoz /> {voz.parcial || "Te escucho… habla con naturalidad"}
            </span>
          ) : (
            <span className="chip bad">{voz.error}</span>
          )}
        </div>
      )}

      <div className="chat-entrada">
        {vozSoportada.escuchar && (
          <button
            className={`btn-mic ${voz.escuchando ? "activo" : ""}`}
            onClick={voz.escuchando ? voz.detener : voz.iniciar}
            aria-label={voz.escuchando ? "Dejar de escuchar" : "Hablarle a Clara"}
            title="Hablarle a Clara"
          >
            {voz.escuchando && (
              <motion.span className="onda" animate={{ scale: [1, 1.5], opacity: [0.7, 0] }} transition={{ duration: 1.2, repeat: Infinity }} />
            )}
            <Mic size={18} />
          </button>
        )}
        <label className="sr-only" htmlFor={compacto ? "chat-compacto" : "chat-pagina"}>
          Escribe tu pregunta
        </label>
        <textarea
          id={compacto ? "chat-compacto" : "chat-pagina"}
          ref={caja}
          rows={1}
          value={valorCaja}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={alTeclear}
          placeholder={compacto ? "Pregúntale a Clara…" : "Pregúntale a Clara… ej. ¿cuánto gané este mes?"}
          maxLength={500}
        />
        {ocupado && !texto.trim() ? (
          <button className="btn icono btn-enviar" onClick={cancelar} aria-label="Detener respuesta" title="Detener respuesta">
            <Square size={16} />
          </button>
        ) : (
          <button className="btn primario btn-enviar" onClick={mandar} disabled={!texto.trim()} aria-label="Enviar pregunta">
            <Send size={17} />
          </button>
        )}
      </div>
      <p className="aviso-ia">Orientación general, no constituye asesoría financiera, contable ni fiscal.</p>
    </div>
  );
}
