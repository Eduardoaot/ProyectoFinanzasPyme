import { motion } from "framer-motion";
import { Calculator, ChartColumnBig, PieChart as IconoPie, Scale, TrendingUp } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CATEGORICOS, EJE, Leyenda, SERIE, TooltipGrafica } from "../components/charts/comun";
import { Aviso, Ayuda, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { Pagina } from "../components/ui/Pagina";
import { usePeriodo } from "../context/Periodo";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { dinero, dineroCompacto, pct } from "../lib/formato";
import { ultimosMeses } from "../lib/periodos";
import type { CategoriaGasto, Finanzas as TipoFinanzas, PuntoSerie } from "../lib/tipos";

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
  const maxMedidor = pe && pe.punto_equilibrio_mensual ? Math.max(pe.punto_equilibrio_mensual, pe.ventas_mensuales_promedio) * 1.15 : 1;

  return (
    <Pagina eyebrow="Finanzas" titulo="¿Estás ganando?"
      descripcion="Tu estado de resultados en palabras sencillas: lo que vendiste, lo que te costó y lo que te quedó. Pasa el cursor sobre ⓘ para ver el término contable.">
      {fz.error && <Aviso tipo="error">{fz.error}</Aviso>}
      <div className="grid grid-2">
        {f ? (
          <Tarjeta>
            <TituloTarjeta icono={Calculator} titulo="Estado de resultados" sub={f.periodo.etiqueta} />
            <div>
              {f.estado_resultados.map((l, i) => {
                const ancho = l.porcentaje !== null ? Math.min(Math.abs(l.porcentaje), 1) * 100 : 0;
                const color = l.nivel === "resta" ? SERIE.gastos : l.clave === "ventas" ? SERIE.ventas : SERIE.utilidad;
                return (
                  <motion.div key={l.clave} className={`er-linea ${l.nivel}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
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
              <TituloTarjeta icono={IconoPie} titulo="¿En qué se va tu dinero?" sub="Gastos de operación por categoría" />
              {gastos.length === 0 ? (
                <p className="muted pequeno">Sin gastos en este periodo.</p>
              ) : (
                <div className="fila envolver" style={{ alignItems: "center", gap: 20 }}>
                  <div style={{ width: 170, height: 170, flex: "none" }}>
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={gastos} dataKey="monto" nameKey="categoria" innerRadius={52} outerRadius={80} paddingAngle={2} stroke="var(--surface)" strokeWidth={2} animationDuration={900}>
                          {gastos.map((g, i) => <Cell key={g.categoria} fill={CATEGORICOS[i]} />)}
                        </Pie>
                        <Tooltip content={<TooltipGrafica titulo={(_, p) => String(p?.categoria ?? "")} />} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="pila" style={{ flex: 1, minWidth: 200, gap: 8 }}>
                    {gastos.map((g, i) => (
                      <div key={g.categoria} className="fila-entre pequeno">
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
                <BarChart data={datosMensual} barGap={2} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
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
        </Tarjeta>

        <Tarjeta retraso={0.16}>
          <TituloTarjeta icono={TrendingUp} titulo="Lo que ganaste cada mes" sub="Utilidad mensual, últimos 12 meses" />
          <div style={{ height: 284 }}>
            {mensual.datos ? (
              <ResponsiveContainer>
                <LineChart data={datosMensual} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
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
        </Tarjeta>
      </div>
    </Pagina>
  );
}
