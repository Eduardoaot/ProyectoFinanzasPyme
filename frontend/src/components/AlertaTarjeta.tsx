import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Lightbulb, OctagonAlert, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import type { Alerta } from "../lib/tipos";

const NIVEL = {
  rojo: { Icono: OctagonAlert, texto: "Acción" },
  amarillo: { Icono: TriangleAlert, texto: "Atención" },
  verde: { Icono: CheckCircle2, texto: "Bien" },
} as const;

const RUTA = { resumen: "/", finanzas: "/finanzas", productos: "/productos", flujo: "/flujo" } as const;

export function TarjetaAlerta({ alerta, indice = 0, compacta = false, redactando = false }: {
  alerta: Alerta;
  indice?: number;
  compacta?: boolean;
  redactando?: boolean;
}) {
  const { Icono, texto } = NIVEL[alerta.nivel];
  return (
    <motion.article
      className={`alerta ${alerta.nivel}`}
      layout
      initial={{ opacity: 0, x: -14 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: indice * 0.06, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      <span className="icono" aria-hidden="true">
        <Icono size={19} />
      </span>
      <div style={{ minWidth: 0 }}>
        <div className="fila-entre" style={{ alignItems: "flex-start" }}>
          <h3>{alerta.titulo}</h3>
          <span className={`semaforo ${alerta.nivel}`}>
            <Icono size={12} aria-hidden="true" />
            {texto}
          </span>
        </div>
        <AnimatePresence mode="wait">
          <motion.p key={alerta.mensaje} className="mensaje justificado" initial={{ opacity: 0 }} animate={{ opacity: redactando ? 0.5 : 1 }} exit={{ opacity: 0 }}>
            {alerta.mensaje}
          </motion.p>
        </AnimatePresence>
        {!compacta && (
          <>
            <p className="accion justificado">
              <Lightbulb size={15} style={{ flex: "none", marginTop: 2 }} color="var(--celeste)" aria-hidden="true" />
              {alerta.accion}
            </p>
            <div className="fila envolver" style={{ marginTop: 10 }}>
              <Link to={RUTA[alerta.modulo]} className="btn chico fantasma">
                Ver detalle <ArrowRight size={14} />
              </Link>
            </div>
          </>
        )}
      </div>
    </motion.article>
  );
}
