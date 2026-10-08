import { motion } from "framer-motion";
import { ArrowRight, FileSpreadsheet, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EJE, SERIE, TooltipGrafica } from "../components/charts/comun";
import { TarjetaAlerta } from "../components/AlertaTarjeta";
import { Aviso, Ayuda, Cambio, EstadoVacio, NumeroAnimado, Segmentado, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { KpiCard, type PuntoSpark } from "../components/ui/KpiCard";
import { Pagina } from "../components/ui/Pagina";
import { useChat } from "../context/Chat";
import { usePeriodo } from "../context/Periodo";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { dinero, dineroCompacto, fechaCorta, numero, pct } from "../lib/formato";
import type { Alerta, DatoClave, KPIs, PuntoSerie, Resumen as TipoResumen, Variaciones } from "../lib/tipos";

type Metrica = "ventas" | "utilidad" | "gastos";

/** Granularidad de la gráfica según la duración del periodo elegido en la barra superior. */
function granularidadDe(desde: string | undefined, hasta: string | undefined): "dia" | "semana" | "mes" {
  if (!desde || !hasta) return "dia";
  const dias = Math.round((Date.parse(hasta) - Date.parse(desde)) / 86400000);
  return dias <= 62 ? "dia" : dias <= 190 ? "semana" : "mes";
}

/** Cada métrica de la gráfica sabe de dónde sacar su total y su cambio en la respuesta de /resumen. */
const METRICAS: Record<Metrica, { texto: string; color: string; kpi: keyof KPIs; variacion: keyof Variaciones; invertido: boolean }> = {
  ventas: { texto: "Ventas", color: SERIE.ventas, kpi: "ventas", variacion: "ventas", invertido: false },
  utilidad: { texto: "Ganancia", color: SERIE.utilidad, kpi: "utilidad", variacion: "utilidad", invertido: false },
  gastos: { texto: "Gastos", color: SERIE.gastos, kpi: "gastos_operacion", variacion: "gastos_operacion", invertido: true },
};

const enteros = (n: number) => dinero(Math.round(n), false);

function valorDato(d: DatoClave): string {
  if (d.valor === null) return "—";
  if (d.formato === "dinero") return dinero(Number(d.valor));
  if (d.formato === "porcentaje") return pct(Number(d.valor));
  if (d.formato === "numero") return numero(Number(d.valor));
  return String(d.valor);
}

/** Bloque principal: la cifra grande, su cambio y la gráfica responden al filtro de
 * periodo de la barra superior (1 mes … 2 años). */
function BloquePrincipal({ idEmpresa, totales }: { idEmpresa: number; totales: TipoResumen | null }) {
  const { params } = usePeriodo();
  const [metrica, setMetrica] = useState<Metrica>("ventas");
  const granularidad = granularidadDe(params.desde, params.hasta);
  const serie = useApi<PuntoSerie[]>(params.desde ? `/empresas/${idEmpresa}/serie` : null, { ...params, granularidad });
  const m = METRICAS[metrica];
  const t = totales;
  const actual = t ? Number(t.kpis[m.kpi]) : null;
  const anterior = t ? Number(t.kpis_anterior[m.kpi]) : null;
  const variacion = t ? t.variaciones[m.variacion] : null;

  return (
    <>
      <div className="fila-entre envolver" style={{ alignItems: "flex-start" }}>
        <div className="pila" style={{ gap: 6 }}>
          <span className="eyebrow">{m.texto} · del {fechaCorta(params.desde ?? "")} al {fechaCorta(params.hasta ?? "")}</span>
          <div className="hero-cifra">
            <span className="grande" style={{ color: actual !== null && actual < 0 ? "var(--bad-ink)" : undefined }}>
              {actual === null ? "—" : <NumeroAnimado valor={actual} formato={enteros} />}
            </span>
            {t && <Cambio valor={variacion} invertido={m.invertido} />}
          </div>
          <span className="pequeno muted num">
            {t && anterior !== null ? (anterior === 0 ? "Sin comparación" : <>vs {dinero(anterior)} en {t.periodo_anterior.etiqueta}</>) : ""}
          </span>
        </div>
        <div className="pila" style={{ alignItems: "flex-end", gap: 8 }}>
          <Segmentado<Metrica> etiqueta="Qué ver" valor={metrica} onChange={setMetrica}
            opciones={(Object.keys(METRICAS) as Metrica[]).map((k) => ({ valor: k, texto: METRICAS[k].texto }))} />
        </div>
      </div>
      <div className="hero-grafica">
        {serie.datos && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={serie.datos} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
              <defs>
                <linearGradient id="g-principal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={m.color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={m.color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="etiqueta" {...EJE} minTickGap={28} />
              <YAxis {...EJE} width={64} tickFormatter={(v) => dineroCompacto(v)} />
              <Tooltip content={<TooltipGrafica nombres={{ [metrica]: m.texto }} />} cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} />
                <Area key={`${metrica}-${granularidad}`} type="monotone" dataKey={metrica} stroke={m.color} strokeWidth={2} fill="url(#g-principal)"
                  activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--surface)" }} animationDuration={900} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </>
  );
}

export function Resumen() {
  const { empresa } = useSesion();
  const { params, seleccion } = usePeriodo();
  const { abrirChat, enviar } = useChat();
  const id = empresa?.id_empresa;
  const listo = Boolean(id && empresa?.tiene_datos && params.desde);
  const resumen = useApi<TipoResumen>(listo ? `/empresas/${id}/resumen` : null, params);
  const alertas = useApi<Alerta[]>(listo ? `/empresas/${id}/alertas` : null, params);

  if (empresa && !empresa.tiene_datos) {
    return (
      <Pagina eyebrow={empresa.nombre_negocio} titulo="Resumen">
        <EstadoVacio icono={FileSpreadsheet} titulo="Sube tu primer Excel para empezar"
          texto="Con tus ventas, productos, compras y gastos armamos tu panel: cuánto ganas, qué producto te deja más y si te alcanza el efectivo. Te guiamos paso a paso."
          accion={<Link to="/importar" className="btn primario">Ver tutorial y subir archivo <ArrowRight size={16} /></Link>} />
      </Pagina>
    );
  }

  const r = resumen.datos;
  const k = r?.kpis;
  const ka = r?.kpis_anterior;
  const v = r?.variaciones;
  const ant = r?.periodo_anterior.etiqueta ?? "";
  const serie = (campo: keyof PuntoSerie): PuntoSpark[] => r?.serie.map((p) => ({ etiqueta: p.etiqueta, valor: Number(p[campo]) })) ?? [];
  const vs = (valor: number | null | undefined, formato: (n: number) => string = dinero) =>
    valor === null || valor === undefined ? undefined : `vs ${formato(valor)} en ${ant}`;

  return (
    <Pagina titulo="Resumen"
      descripcion={r ? `${r.periodo.etiqueta} · comparado con ${ant}` : undefined}
      acciones={
        <button className="btn" onClick={() => {
          abrirChat();
          enviar(`Hazme un análisis completo de ${seleccion?.etiqueta ?? "este periodo"}`);
        }}>
          <Sparkles size={16} color="var(--celeste)" /> Análisis con Clara
        </button>
      }>

      {resumen.error && <Aviso tipo="error">{resumen.error}</Aviso>}

      <div className="hero-ventas">
        <Tarjeta interactiva={false}>
          {id && <BloquePrincipal idEmpresa={id} totales={r} />}
        </Tarjeta>

        <Tarjeta retraso={0.08}>
          <TituloTarjeta titulo="Datos clave" sub={r?.periodo.etiqueta} />
          <div className="datos-clave">
            {(r?.datos_clave ?? Array.from({ length: 8 }, () => null)).map((d, i) =>
              d ? (
                <motion.div className="dato" key={d.etiqueta} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.04 }}>
                  <span className="k">{d.etiqueta}{d.ayuda && <Ayuda texto={d.ayuda} />}</span>
                  <span className="v num">{valorDato(d)}</span>
                </motion.div>
              ) : (
                <div className="dato" key={i}><span className="esqueleto" style={{ height: 14, width: "100%" }} /></div>
              ),
            )}
          </div>
        </Tarjeta>
      </div>

      {k && ka && v ? (
        <div className="grid grid-kpi">
          <KpiCard indice={0} etiqueta="Vendiste" tecnico="Ventas netas" valor={k.ventas} formato={enteros}
            variacion={v.ventas} comparacion={vs(ka.ventas)} serie={serie("ventas")} color={SERIE.ventas} />
          <KpiCard indice={1} etiqueta="Costo de mercancía" tecnico="Costo de ventas: lo que te costó la mercancía que vendiste" valor={k.costo_ventas} formato={enteros}
            variacion={v.costo_ventas} invertido comparacion={vs(ka.costo_ventas)} serie={serie("costo")} color={SERIE.gastos} />
          <KpiCard indice={2} etiqueta="Ganancia bruta" tecnico="Utilidad bruta = ventas − costo de ventas" valor={k.utilidad_bruta} formato={enteros}
            variacion={v.utilidad_bruta} comparacion={vs(ka.utilidad_bruta)} serie={serie("utilidad_bruta")} color={SERIE.utilidad} />
          <KpiCard indice={3} etiqueta="Gastos del negocio" tecnico="Gastos de operación (fijos + variables)" valor={k.gastos_operacion} formato={enteros}
            variacion={v.gastos_operacion} invertido comparacion={vs(ka.gastos_operacion)} serie={serie("gastos")} color={SERIE.gastos} />
          <KpiCard indice={4} etiqueta="Lo que ganaste" tecnico="Utilidad (antes de impuestos)" valor={k.utilidad} formato={enteros}
            variacion={v.utilidad} comparacion={vs(ka.utilidad)} serie={serie("utilidad")} color={SERIE.utilidad} />
          <KpiCard indice={5} etiqueta="Margen" tecnico="Margen = utilidad / ventas" valor={k.margen === null ? null : k.margen * 100}
            formato={(n) => `${n.toFixed(1)}%`} puntos={v.margen_pp} comparacion={vs(ka.margen, (n) => pct(n))}
            nota={k.margen !== null ? `de cada $100 te quedan ${dinero(k.margen * 100)}` : undefined} />
        </div>
      ) : (
        <div className="grid grid-kpi">{Array.from({ length: 6 }, (_, i) => <TarjetaCargando key={i} alto={60} />)}</div>
      )}

      <Tarjeta retraso={0.15}>
        <TituloTarjeta titulo="Lo que necesita tu atención" sub="Avisos calculados con tus datos"
          derecha={<Link to="/alertas" className="btn chico">Ver todas <ArrowRight size={14} /></Link>} />
        <div className="pila">
          {alertas.cargando && !alertas.datos && <TarjetaCargando alto={60} />}
          {alertas.datos?.slice(0, 3).map((a, i) => <TarjetaAlerta key={a.id} alerta={a} indice={i} compacta />)}
          {alertas.datos?.length === 0 && <p className="muted pequeno">Todo en orden: no hay alertas en este periodo.</p>}
        </div>
      </Tarjeta>
    </Pagina>
  );
}
