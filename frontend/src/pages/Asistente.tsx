import { motion } from "framer-motion";
import { BadgeCheck, Calculator, Mic, ShieldCheck, Volume2 } from "lucide-react";
import { Conversacion } from "../components/chat/Conversacion";
import { Tarjeta, TituloTarjeta } from "../components/ui/basicos";
import { Pagina } from "../components/ui/Pagina";
import { useChat } from "../context/Chat";

const CAPACIDADES = [
  { pregunta: "¿Estoy ganando?", ejemplo: "¿Cuánto gané en agosto?" },
  { pregunta: "¿Qué producto me deja más?", ejemplo: "¿Qué productos me dejan menos?" },
  { pregunta: "¿Dónde gasto demasiado?", ejemplo: "¿En qué se va mi dinero este año?" },
  { pregunta: "¿Me va a alcanzar el efectivo?", ejemplo: "¿Debería pedir un préstamo?" },
  { pregunta: "Inventario", ejemplo: "¿Qué se me va a agotar?" },
  { pregunta: "Diagnóstico", ejemplo: "Hazme un análisis completo" },
  { pregunta: "Comparar", ejemplo: "Compara mis ventas con el mes pasado" },
  { pregunta: "Proyección", ejemplo: "¿Cuánto voy a vender el próximo mes?" },
];

export function Asistente() {
  const { enviar } = useChat();
  return (
    <Pagina titulo="Asistente Clara"
      descripcion="Preguntas sobre ventas, gastos, productos o efectivo, por texto o por voz. Puedes indicar el periodo: “en agosto”, “el mes pasado”, “este año”.">
      <div className="grid grid-lateral">
        <motion.div className="card" style={{ padding: 0, height: "min(760px, calc(100dvh - 210px))", minHeight: 520, overflow: "hidden" }}
          initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
          <Conversacion />
        </motion.div>
        <div className="pila" style={{ gap: "var(--sp-5)" }}>
          <Tarjeta retraso={0.08}>
            <TituloTarjeta icono={BadgeCheck} titulo="Puedes preguntarle" sub="Toca un ejemplo para probar" />
            <div className="pila" style={{ gap: 8 }}>
              {CAPACIDADES.map((c, i) => (
                <motion.button key={c.ejemplo} className="chip boton" style={{ justifyContent: "space-between", padding: "8px 12px", borderRadius: 10, whiteSpace: "normal", textAlign: "left" }}
                  onClick={() => enviar(c.ejemplo)}
                  initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.04 }}>
                  <span>{c.ejemplo}</span>
                  <span className="mini muted">{c.pregunta}</span>
                </motion.button>
              ))}
            </div>
          </Tarjeta>
          <Tarjeta retraso={0.14}>
            <TituloTarjeta icono={ShieldCheck} titulo="Cómo funciona" />
            <ul className="pila pequeno" style={{ margin: 0, padding: 0, listStyle: "none", gap: 12 }}>
              <li className="fila" style={{ alignItems: "flex-start" }}>
                <Calculator size={16} color="var(--celeste)" style={{ flex: "none", marginTop: 3 }} />
                <span className="justificado">Las cifras las calcula el sistema con SQL y Python. La IA local (Ollama) solo las explica, y un filtro descarta cualquier número que no venga de tus datos.</span>
              </li>
              <li className="fila" style={{ alignItems: "flex-start" }}>
                <Mic size={16} color="var(--celeste)" style={{ flex: "none", marginTop: 3 }} />
                <span className="justificado">Toca el micrófono y habla en español. Funciona en Chrome y Edge.</span>
              </li>
              <li className="fila" style={{ alignItems: "flex-start" }}>
                <Volume2 size={16} color="var(--celeste)" style={{ flex: "none", marginTop: 3 }} />
                <span className="justificado">Clara lee sus respuestas en voz alta. Puedes apagarlo con el botón de bocina.</span>
              </li>
            </ul>
          </Tarjeta>
        </div>
      </div>
    </Pagina>
  );
}
