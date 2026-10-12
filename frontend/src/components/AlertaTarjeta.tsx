import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CheckCircle2, Lightbulb, OctagonAlert, TriangleAlert } from "lucide-react";
import { useState, type KeyboardEvent, type MouseEvent } from "react";
import { Link } from "react-router-dom";
import type { Alerta } from "../lib/tipos";
import { BotonClara, Emergente, IrASeccion, ListaCifras } from "./ui/Emergente";

const NIVEL = {
  rojo: { Icono: OctagonAlert, texto: "Acción" },
  amarillo: { Icono: TriangleAlert, texto: "Atención" },
  verde: { Icono: CheckCircle2, texto: "Bien" },
} as const;

const RUTA = {
  resumen: "/resumen", finanzas: "/finanzas", productos: "/productos", flujo: "/flujo",
  proyecciones: "/proyecciones", impuestos: "/impuestos", deudas: "/deudas",
} as const;

// Nombres en palabras de todos los días para las cifras que acompañan a cada alerta.
const NOMBRE_METRICA: Record<string, string> = {
  periodo: "Periodo", periodo_anterior: "Periodo anterior", ventas: "Vendiste", ventas_anterior: "Vendiste antes",
  perdida: "Perdiste", margen: "Margen", umbral: "Límite del aviso", de_cada_100: "De cada $100 te quedan",
  utilidad: "Lo que ganaste", gastos_operacion: "Gastos del negocio", gastos: "Gastos del negocio", cambio: "Cambio",
  cambio_gastos: "Cambio en gastos", cambio_ventas: "Cambio en ventas", producto: "Producto", precio: "Precio",
  costo: "Costo", ganancia_unitaria: "Te deja por pieza", cantidad: "Productos", productos: "Cuáles",
};

const nombreMetrica = (k: string) => NOMBRE_METRICA[k] ?? k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, " ");

function DetalleAlerta({ alerta, onCerrar }: { alerta: Alerta; onCerrar: () => void }) {
  const { Icono, texto } = NIVEL[alerta.nivel];
  const cifras = Object.entries(alerta.metricas);
  return (
    <Emergente icono={Icono} titulo={alerta.titulo} subtitulo={<span className={`semaforo ${alerta.nivel}`}><Icono size={12} aria-hidden="true" />{texto}</span>}
      onCerrar={onCerrar}
      pie={<>
        <BotonClara pregunta={`Explícame este aviso y qué puedo hacer: ${alerta.titulo}`} antes={onCerrar} />
        <IrASeccion a={RUTA[alerta.modulo]} />
      </>}>
      <p>{alerta.mensaje}</p>
      <p className="emergente-explica fila" style={{ gap: 8, alignItems: "flex-start" }}>
        <Lightbulb size={16} style={{ flex: "none", marginTop: 3 }} color="var(--celeste)" aria-hidden="true" />
        <span><strong>Qué puedes hacer:</strong> {alerta.accion}</span>
      </p>
      {cifras.length > 0 && (
        <>
          <h3 className="pequeno">Las cifras de este aviso</h3>
          <ListaCifras filas={cifras.map(([k, v]) => ({ nombre: nombreMetrica(k), valor: v }))} />
        </>
      )}
      {alerta.redactado_por_ia && <p className="mini muted">Texto redactado por IA con las cifras calculadas por el sistema.</p>}
    </Emergente>
  );
}

export function TarjetaAlerta({ alerta, indice = 0, compacta = false, redactando = false }: {
  alerta: Alerta;
  indice?: number;
  compacta?: boolean;
  redactando?: boolean;
}) {
  const { Icono, texto } = NIVEL[alerta.nivel];
  const [abierta, setAbierta] = useState(false);
  // Picar la alerta abre su detalle; los enlaces de adentro siguen funcionando como enlaces.
  const alPicar = (e: MouseEvent) => {
    if (!(e.target as HTMLElement).closest("a, button")) setAbierta(true);
  };
  const alTeclear = (e: KeyboardEvent) => {
    if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      setAbierta(true);
    }
  };
  return (
    <>
      <motion.article
        className={`alerta ${alerta.nivel} picable`}
        layout
        tabIndex={0}
        aria-haspopup="dialog"
        aria-label={`${alerta.titulo}. Abrir detalle`}
        onClick={alPicar}
        onKeyDown={alTeclear}
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
      <AnimatePresence>{abierta && <DetalleAlerta alerta={alerta} onCerrar={() => setAbierta(false)} />}</AnimatePresence>
    </>
  );
}
