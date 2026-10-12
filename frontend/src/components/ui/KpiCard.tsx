import { AnimatePresence, motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, ChartNoAxesColumn, Maximize2, Minus } from "lucide-react";
import { useState, type MouseEvent } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EJE } from "../charts/comun";
import { Ayuda, Cambio, NumeroAnimado } from "./basicos";
import { BotonClara, Emergente, ListaCifras } from "./Emergente";

export interface PuntoSpark {
  etiqueta: string;
  valor: number;
}

interface Props {
  etiqueta: string;
  tecnico?: string;
  valor: number | null;
  formato: (n: number) => string;
  variacion?: number | null;
  /** Cambio en puntos porcentuales (para márgenes), en lugar de % relativo. */
  puntos?: number | null;
  invertido?: boolean;
  /** Texto bajo el cambio, p. ej. "vs $42,335 en agosto 2026". */
  comparacion?: string;
  serie?: PuntoSpark[];
  color?: string;
  indice?: number;
  nota?: string;
  /** Lo que se le pregunta a Clara desde el detalle; si falta, se arma con la etiqueta. */
  pregunta?: string;
}

function ChipPuntos({ valor }: { valor: number | null }) {
  if (valor === null) return <span className="cambio neutro">sin comparación</span>;
  const Icono = valor > 0 ? ArrowUpRight : valor < 0 ? ArrowDownRight : Minus;
  const clase = Math.abs(valor) < 0.0005 ? "neutro" : valor > 0 ? "sube" : "baja";
  return (
    <span className={`cambio ${clase} num`}>
      <Icono size={13} aria-hidden="true" />
      {valor > 0 ? "+" : valor < 0 ? "−" : ""}
      {Math.abs(valor * 100).toFixed(1)} pts
    </span>
  );
}

function TooltipSpark({ active, payload, formato }: { active?: boolean; payload?: { payload: PuntoSpark }[]; formato: (n: number) => string }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tooltip-spark">
      <span className="muted">{p.etiqueta}</span>
      <strong className="num">{formato(p.valor)}</strong>
    </div>
  );
}

/** Mayor, menor y promedio de la mini tendencia: aritmética simple hecha en el navegador sobre cifras del backend. */
function extremos(serie: PuntoSpark[]) {
  const mayor = serie.reduce((a, b) => (b.valor > a.valor ? b : a));
  const menor = serie.reduce((a, b) => (b.valor < a.valor ? b : a));
  const promedio = serie.reduce((s, p) => s + p.valor, 0) / serie.length;
  return { mayor, menor, promedio };
}

function DetalleKpi({ p, onCerrar }: { p: Props; onCerrar: () => void }) {
  const { etiqueta, tecnico, valor, formato, variacion, puntos, invertido, comparacion, serie, color = "var(--s1)", nota } = p;
  const hayTendencia = serie && serie.length > 1;
  const ex = hayTendencia ? extremos(serie) : null;
  return (
    <Emergente variante="lado" icono={ChartNoAxesColumn} titulo={etiqueta} subtitulo={comparacion} onCerrar={onCerrar}
      pie={<BotonClara pregunta={p.pregunta ?? `¿Qué significa ${etiqueta.toLowerCase()}?`} antes={onCerrar} />}>
      <div className="emergente-cifra">
        <strong>{valor === null ? "—" : formato(valor)}</strong>
        {variacion !== undefined && <Cambio valor={variacion} invertido={invertido} />}
        {puntos !== undefined && <ChipPuntos valor={puntos} />}
      </div>
      {nota && <p className="muted">{nota}</p>}
      {tecnico && <p className="emergente-explica"><strong>¿Qué es?</strong> {tecnico}</p>}
      {hayTendencia && ex && (
        <>
          <h3 className="pequeno">Cómo ha cambiado</h3>
          <div className="emergente-grafica">
            <ResponsiveContainer>
              <AreaChart data={serie} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="g-detalle-kpi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="etiqueta" {...EJE} minTickGap={24} />
                <YAxis {...EJE} width={60} tickFormatter={(v: number) => formato(v)} />
                <Tooltip content={<TooltipSpark formato={formato} />} cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} />
                <Area type="monotone" dataKey="valor" stroke={color} strokeWidth={2} fill="url(#g-detalle-kpi)" animationDuration={700}
                  activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2, fill: color }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <ListaCifras filas={[
            { nombre: `Más alto (${ex.mayor.etiqueta})`, valor: formato(ex.mayor.valor) },
            { nombre: `Más bajo (${ex.menor.etiqueta})`, valor: formato(ex.menor.valor) },
            { nombre: "Promedio", valor: formato(ex.promedio) },
          ]} />
        </>
      )}
    </Emergente>
  );
}

/** Tarjeta KPI centrada: etiqueta sencilla, término técnico en tooltip, cifra animada,
 * cambio contra el periodo anterior y mini tendencia que muestra el dato al tocarla. */
export function KpiCard(props: Props) {
  const {
    etiqueta, tecnico, valor, formato, variacion, puntos, invertido, comparacion, serie, color = "var(--s1)", indice = 0, nota,
  } = props;
  const [abierto, setAbierto] = useState(false);
  const id = `spark-${etiqueta.replace(/\W/g, "")}`;
  // Picar la tarjeta abre el detalle; el globo de ayuda conserva su propio comportamiento.
  const alPicar = (e: MouseEvent) => {
    if (!(e.target as HTMLElement).closest(".ayuda, .kpi-abrir")) setAbierto(true);
  };
  return (
    <>
    <motion.article
      className="card kpi interactiva picable"
      onClick={alPicar}
      initial={{ opacity: 0, y: 18, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      whileHover={{ y: -3 }}
      transition={{ duration: 0.5, delay: indice * 0.06, ease: [0.22, 1, 0.36, 1] }}
    >
      <button type="button" className="kpi-abrir" onClick={() => setAbierto(true)} aria-label={`Ver detalle de ${etiqueta}`} title="Ver detalle">
        <Maximize2 size={14} aria-hidden="true" />
      </button>
      <span className="etiqueta">
        {etiqueta}
        {tecnico && <Ayuda texto={tecnico} />}
      </span>
      <strong className="valor">{valor === null ? "—" : <NumeroAnimado valor={valor} formato={formato} />}</strong>
      {variacion !== undefined && <Cambio valor={variacion} invertido={invertido} />}
      {puntos !== undefined && <ChipPuntos valor={puntos} />}
      {comparacion && <span className="mini muted num">{comparacion}</span>}
      {nota && <span className="mini muted">{nota}</span>}
      {serie && serie.length > 1 && (
        <div className="spark" aria-label={`Tendencia de ${etiqueta.toLowerCase()}: toca la gráfica para ver cada dato`}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={serie} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
              <defs>
                <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Tooltip
                content={<TooltipSpark formato={formato} />}
                cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
                allowEscapeViewBox={{ x: true, y: true }}
                wrapperStyle={{ zIndex: 20, pointerEvents: "none" }}
                offset={12}
              />
              <Area type="monotone" dataKey="valor" stroke={color} strokeWidth={2} fill={`url(#${id})`} animationDuration={900}
                activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2, fill: color }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </motion.article>
    <AnimatePresence>{abierto && <DetalleKpi p={props} onCerrar={() => setAbierto(false)} />}</AnimatePresence>
    </>
  );
}
