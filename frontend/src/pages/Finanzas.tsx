import { AnimatePresence, motion } from "framer-motion";
import { CalendarDays, Calculator, ChartColumnBig, MousePointerClick, PieChart as IconoPie, Scale, TrendingUp } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CATEGORICOS, EJE, indicePicado, Leyenda, SERIE, TooltipGrafica } from "../components/charts/comun";
import { Aviso, Ayuda, Cambio, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { BotonClara, Emergente, ListaCifras } from "../components/ui/Emergente";
import { Pagina } from "../components/ui/Pagina";
import { usePeriodo } from "../context/Periodo";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { dinero, dineroCompacto, pct } from "../lib/formato";
import { mesLargo, ultimosMeses } from "../lib/periodos";
import type { CategoriaGasto, Finanzas as TipoFinanzas, LineaEstado, PuntoSerie } from "../lib/tipos";

const cambioContra = (actual: number, antes: number | undefined) =>
  antes === undefined || antes === 0 ? null : (actual - antes) / Math.abs(antes);

/** Enter o espacio sobre un elemento "picable" que no es botón. */
const conTeclado = (accion: () => void) => (e: KeyboardEvent) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    accion();
  }
};

/** Detalle de un mes al picarlo en las gráficas: las cifras de ese mes y cómo cambió contra el anterior. */
function DetalleMes({ meses, i, onCerrar }: { meses: PuntoSerie[]; i: number; onCerrar: () => void }) {
  const p = meses[i];
  const ant = meses[i - 1];
  const margen = p.ventas ? p.utilidad / p.ventas : null;
  return (
    <Emergente ancho="chico" icono={CalendarDays} titulo={mesLargo(p.periodo).replace(/^./, (c) => c.toUpperCase())}
      subtitulo={ant ? `Comparado con ${ant.etiqueta}` : undefined} onCerrar={onCerrar}
      pie={<BotonClara pregunta={`¿Cuánto gané en ${mesLargo(p.periodo)}?`} antes={onCerrar} />}>
      <div className="emergente-cifra">
        <strong style={{ color: p.utilidad < 0 ? "var(--bad-ink)" : undefined }}>{dinero(p.utilidad)}</strong>
        <Cambio valor={cambioContra(p.utilidad, ant?.utilidad)} />
      </div>
      <p className="muted">{p.utilidad < 0 ? "Perdiste este mes." : "Es lo que ganaste este mes, después de mercancía y gastos."}</p>
      <ListaCifras filas={[
        { nombre: <>Vendiste {ant && <Cambio valor={cambioContra(p.ventas, ant.ventas)} />}</>, valor: dinero(p.ventas) },
        { nombre: "Mercancía que vendiste", valor: `− ${dinero(p.costo)}` },
        { nombre: "Gastos del negocio", valor: `− ${dinero(p.gastos)}` },
        { nombre: "Ganancia bruta", valor: dinero(p.utilidad_bruta) },
        { nombre: "Lo que ganaste", valor: dinero(p.utilidad), tono: p.utilidad < 0 ? "mal" : "bien" },
        { nombre: "Margen", valor: margen === null ? "—" : pct(margen) },
      ]} />
    </Emergente>
  );
}

function agruparGastos(lista: CategoriaGasto[]) {
  // Máximo 5 categorías con color propio; el resto se suma en "Otros" (nunca se generan colores nuevos).
  const principales = lista.slice(0, 5);
  const resto = lista.slice(5);
  const otros = resto.reduce((s, g) => s + g.monto, 0);
  const total = lista.reduce((s, g) => s + g.monto, 0);
  return otros > 0
    ? [...principales, { categoria: "Otros", tipo: "mixto", monto: otros, porcentaje: total ? otros / total : 0 }]
    : principales;
}

export function Finanzas() {
  const { empresa } = useSesion();
  const { params, seleccion } = usePeriodo();
  const id = empresa?.id_empresa;
  const listo = Boolean(id && empresa?.tiene_datos && params.desde);
  const fz = useApi<TipoFinanzas>(listo ? `/empresas/${id}/finanzas` : null, params);
  const rango12 = seleccion && empresa?.primer_dato ? ultimosMeses(seleccion.hasta, 12, empresa.primer_dato) : null;
  const mensual = useApi<PuntoSerie[]>(listo && rango12 ? `/empresas/${id}/serie` : null, { ...rango12, granularidad: "mes" });

  const f = fz.datos;
  const pe = f?.punto_equilibrio;
  const gastos = f ? agruparGastos(f.distribucion_gastos) : [];
  const datosMensual = (mensual.datos ?? []).map((p) => ({ ...p, salidas: p.costo + p.gastos }));
  const [mes, setMes] = useState<number | null>(null);
  const [gasto, setGasto] = useState<(CategoriaGasto & { color: string }) | null>(null);
  const [linea, setLinea] = useState<LineaEstado | null>(null);
  const totalGastos = gastos.reduce((s, g) => s + g.monto, 0);
  const maxMedidor = pe && pe.punto_equilibrio_mensual ? Math.max(pe.punto_equilibrio_mensual, pe.ventas_mensuales_promedio) * 1.15 : 1;

  return (
    <Pagina titulo="Finanzas"
      descripcion={f ? `Ventas, costos, gastos y utilidad · ${f.periodo.etiqueta}.` : undefined}>
      {fz.error && <Aviso tipo="error">{fz.error}</Aviso>}
      <div className="grid grid-2">
        {f ? (
          <Tarjeta>
            <TituloTarjeta icono={Calculator} titulo="Estado de resultados" sub={`${f.periodo.etiqueta} · toca un renglón para ver qué significa`} />
            <div>
              {f.estado_resultados.map((l, i) => {
                const ancho = l.porcentaje !== null ? Math.min(Math.abs(l.porcentaje), 1) * 100 : 0;
                const color = l.nivel === "resta" ? SERIE.gastos : l.clave === "ventas" ? SERIE.ventas : SERIE.utilidad;
                return (
                  <motion.div key={l.clave} className={`er-linea ${l.nivel} picable`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                    role="button" tabIndex={0} aria-haspopup="dialog" aria-label={`${l.etiqueta}: ${l.nota || dinero(l.monto)}. Ver qué significa`}
                    onClick={(e) => !(e.target as HTMLElement).closest(".ayuda") && setLinea(l)}
                    onKeyDown={(e) => e.target === e.currentTarget && conTeclado(() => setLinea(l))(e)}>
                    <span className="fila" style={{ gap: 6 }}>
                      {l.nivel === "resta" ? "− " : ""}
                      {l.etiqueta}
                      <Ayuda texto={l.termino_tecnico} />
                    </span>
                    <span className="monto num" style={{ color: l.monto < 0 ? "var(--bad-ink)" : undefined }}>{l.nota || dinero(l.monto)}</span>
                    <span className="porc num">{l.porcentaje !== null ? pct(l.porcentaje) : ""}</span>
                    {l.nivel !== "info" && l.nivel !== "total" && (
                      <div className="barra-er">
                        <motion.span style={{ background: color }} initial={{ width: 0 }} animate={{ width: `${ancho}%` }} transition={{ delay: 0.2 + i * 0.06, duration: 0.8, ease: [0.22, 1, 0.36, 1] }} />
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          </Tarjeta>
        ) : (
          <TarjetaCargando alto={380} />
        )}

        <div className="pila columna-er" style={{ gap: "var(--sp-5)" }}>
          {pe ? (
            <Tarjeta retraso={0.05}>
              <TituloTarjeta icono={Scale} titulo="Punto de equilibrio" sub="Cuánto necesitas vender al mes para no perder" />
              {pe.punto_equilibrio_mensual === null ? (
                <Aviso>Con el margen actual no se puede calcular: tus costos variables superan tus ventas.</Aviso>
              ) : (
                <>
                  <div className="medidor" role="img"
                    aria-label={`Vendes ${dinero(pe.ventas_mensuales_promedio)} al mes; necesitas ${dinero(pe.punto_equilibrio_mensual)}`}>
                    <motion.div className="relleno" initial={{ width: 0 }} animate={{ width: `${(pe.ventas_mensuales_promedio / maxMedidor) * 100}%` }}
                      transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }} />
                    <div className="marca" style={{ left: `${(pe.punto_equilibrio_mensual / maxMedidor) * 100}%` }}>
                      <span>Equilibrio {dineroCompacto(pe.punto_equilibrio_mensual)}</span>
                    </div>
                    <div className="marca abajo" style={{ left: `${(pe.ventas_mensuales_promedio / maxMedidor) * 100}%`, background: "var(--celeste)" }}>
                      <span>Vendes {dineroCompacto(pe.ventas_mensuales_promedio)}</span>
                    </div>
                  </div>
                  <p className="pequeno justificado">
                    {pe.cubierto ? (
                      <>Vas bien: tus ventas superan el punto de equilibrio por <strong>{dinero(pe.margen_seguridad_mensual)}</strong> al mes. Ese es tu <em>margen de seguridad</em>: lo que podrían bajar tus ventas antes de perder.</>
                    ) : (
                      <>Te faltan <strong>{dinero(Math.abs(pe.margen_seguridad_mensual ?? 0))}</strong> al mes para cubrir todos tus gastos.</>
                    )}{" "}
                    De cada $100 que vendes, después de mercancía y gastos variables te quedan {dinero((pe.margen_contribucion ?? 0) * 100)} para pagar tus gastos fijos de {dinero(pe.gastos_fijos_mensuales)} al mes.
                  </p>
                </>
              )}
            </Tarjeta>
          ) : (
            <TarjetaCargando alto={160} />
          )}

          {f ? (
            <Tarjeta retraso={0.1}>
              <TituloTarjeta icono={IconoPie} titulo="Distribución de gastos" sub="Gastos de operación por categoría" />
              {gastos.length === 0 ? (
                <p className="muted pequeno">Sin gastos en este periodo.</p>
              ) : (
                <div className="fila envolver" style={{ alignItems: "center", gap: 20 }}>
                  <div style={{ width: 170, height: 170, flex: "none" }}>
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={gastos} dataKey="monto" nameKey="categoria" innerRadius={52} outerRadius={80} paddingAngle={2} stroke="var(--surface)" strokeWidth={2} animationDuration={900}
                          style={{ cursor: "pointer" }} onClick={(_, i) => setGasto({ ...gastos[i], color: CATEGORICOS[i] })}>
                          {gastos.map((g, i) => <Cell key={g.categoria} fill={CATEGORICOS[i]} />)}
                        </Pie>
                        <Tooltip content={<TooltipGrafica titulo={(_, p) => String(p?.categoria ?? "")} />} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="pila" style={{ flex: 1, minWidth: 200, gap: 8 }}>
                    {gastos.map((g, i) => (
                      <div key={g.categoria} className="fila-entre pequeno fila-picable picable" role="button" tabIndex={0} aria-haspopup="dialog"
                        onClick={() => setGasto({ ...g, color: CATEGORICOS[i] })} onKeyDown={conTeclado(() => setGasto({ ...g, color: CATEGORICOS[i] }))}>
                        <span className="fila" style={{ gap: 8 }}>
                          <i style={{ width: 10, height: 10, borderRadius: 3, background: CATEGORICOS[i], display: "inline-block" }} />
                          {g.categoria}
                        </span>
                        <span className="num"><strong>{dinero(g.monto)}</strong> <span className="muted">· {pct(g.porcentaje, 0)}</span></span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Tarjeta>
          ) : (
            <TarjetaCargando alto={170} />
          )}
        </div>
      </div>

      <div className="grid grid-2">
        <Tarjeta retraso={0.12}>
          <TituloTarjeta icono={ChartColumnBig} titulo="Ingresos vs. gastos por mes" sub="Lo que vendiste contra lo que salió (mercancía + gastos), últimos 12 meses" />
          <Leyenda items={[{ nombre: "Ventas", color: SERIE.ventas }, { nombre: "Mercancía + gastos", color: SERIE.gastos }]} />
          <div style={{ height: 260 }}>
            {mensual.datos ? (
              <ResponsiveContainer>
                <BarChart data={datosMensual} barGap={2} margin={{ top: 4, right: 4, bottom: 0, left: 0 }} onClick={(e) => setMes(indicePicado(e))} style={{ cursor: "pointer" }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="etiqueta" {...EJE} />
                  <YAxis {...EJE} width={60} tickFormatter={dineroCompacto} />
                  <Tooltip content={<TooltipGrafica nombres={{ ventas: "Ventas", salidas: "Mercancía + gastos" }} />} cursor={{ fill: "var(--surface-hover)" }} />
                  <Bar dataKey="ventas" fill={SERIE.ventas} radius={[4, 4, 0, 0]} maxBarSize={22} animationDuration={800} />
                  <Bar dataKey="salidas" fill={SERIE.gastos} radius={[4, 4, 0, 0]} maxBarSize={22} animationDuration={800} animationBegin={150} />
                </BarChart>
              </ResponsiveContainer>
            ) : null}
          </div>
          <p className="pista-grafica"><MousePointerClick size={13} aria-hidden="true" /> Toca un mes para ver su detalle.</p>
        </Tarjeta>

        <Tarjeta retraso={0.16}>
          <TituloTarjeta icono={TrendingUp} titulo="Lo que ganaste cada mes" sub="Utilidad mensual, últimos 12 meses" />
          <div style={{ height: 284 }}>
            {mensual.datos ? (
              <ResponsiveContainer>
                <LineChart data={datosMensual} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} onClick={(e) => setMes(indicePicado(e))} style={{ cursor: "pointer" }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="etiqueta" {...EJE} />
                  <YAxis {...EJE} width={60} tickFormatter={dineroCompacto} />
                  <ReferenceLine y={0} stroke="var(--axis)" />
                  <Tooltip content={<TooltipGrafica nombres={{ utilidad: "Lo que ganaste" }} />} cursor={{ stroke: "var(--axis)" }} />
                  <Line type="monotone" dataKey="utilidad" stroke={SERIE.utilidad} strokeWidth={2} dot={{ r: 4, fill: SERIE.utilidad, stroke: "var(--surface)", strokeWidth: 2 }}
                    activeDot={{ r: 6 }} animationDuration={1000} />
                </LineChart>
              </ResponsiveContainer>
            ) : null}
          </div>
          <p className="pista-grafica"><MousePointerClick size={13} aria-hidden="true" /> Toca un mes para ver su detalle.</p>
        </Tarjeta>
      </div>

      <AnimatePresence>
        {mes !== null && datosMensual[mes] && <DetalleMes key="mes" meses={datosMensual} i={mes} onCerrar={() => setMes(null)} />}
        {gasto && (
          <Emergente key="gasto" ancho="chico" icono={IconoPie} titulo={gasto.categoria} subtitulo={f?.periodo.etiqueta} onCerrar={() => setGasto(null)}
            pie={<BotonClara pregunta="¿En qué gasto más?" antes={() => setGasto(null)} />}>
            <div className="emergente-cifra"><strong>{dinero(gasto.monto)}</strong></div>
            <div className="barra" aria-hidden="true"><span style={{ width: `${gasto.porcentaje * 100}%`, background: gasto.color }} /></div>
            <ListaCifras filas={[
              { nombre: "Parte de tus gastos", valor: pct(gasto.porcentaje, 0) },
              { nombre: "Tipo de gasto", valor: gasto.tipo === "fijo" ? "Fijo (cada mes)" : gasto.tipo === "variable" ? "Variable" : "Varios" },
              { nombre: "Todos tus gastos", valor: dinero(totalGastos) },
            ]} />
          </Emergente>
        )}
        {linea && (
          <Emergente key="linea" ancho="chico" icono={Calculator} titulo={linea.etiqueta} subtitulo={f?.periodo.etiqueta} onCerrar={() => setLinea(null)}
            pie={<BotonClara pregunta={`¿Qué significa ${linea.etiqueta.toLowerCase()}?`} antes={() => setLinea(null)} />}>
            <div className="emergente-cifra">
              <strong style={{ color: linea.monto < 0 ? "var(--bad-ink)" : undefined }}>{linea.nota || dinero(linea.monto)}</strong>
              {linea.porcentaje !== null && <span className="muted">{pct(linea.porcentaje)} de tus ventas</span>}
            </div>
            <p className="emergente-explica"><strong>¿Qué es?</strong> {linea.termino_tecnico}</p>
          </Emergente>
        )}
      </AnimatePresence>
    </Pagina>
  );
}
