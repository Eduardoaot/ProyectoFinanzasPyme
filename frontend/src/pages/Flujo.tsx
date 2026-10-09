import { motion } from "framer-motion";
import { ArrowDownLeft, ArrowUpRight, CalendarClock, ChartColumnBig, Info, Wallet } from "lucide-react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EJE, Leyenda, SERIE, TooltipGrafica } from "../components/charts/comun";
import { Aviso, Semaforo, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { KpiCard } from "../components/ui/KpiCard";
import { Pagina } from "../components/ui/Pagina";
import { usePeriodo } from "../context/Periodo";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { dinero, dineroCompacto, fechaCorta, fechaLarga } from "../lib/formato";
import type { Flujo as TipoFlujo } from "../lib/tipos";

function haceDias(iso: string, dias: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() - dias);
  return d.toISOString().slice(0, 10);
}

export function Flujo() {
  const { empresa } = useSesion();
  const { params } = usePeriodo();
  const id = empresa?.id_empresa;
  const listo = Boolean(id && empresa?.tiene_datos && params.desde);
  const fl = useApi<TipoFlujo>(listo ? `/empresas/${id}/flujo` : null, params);
  const corte = empresa?.ultimo_dato;
  const reciente = useApi<TipoFlujo>(listo && corte ? `/empresas/${id}/flujo` : null, corte ? { desde: haceDias(corte, 59), hasta: corte } : undefined);

  const f = fl.datos;
  const proy = reciente.datos?.proyeccion;
  const datosProy = reciente.datos && proy
    ? [
        ...reciente.datos.diario.map((d) => ({ fecha: d.fecha, saldo: d.saldo })),
        { fecha: proy.fecha_corte, proyectado: proy.saldo_actual, rango: [proy.saldo_actual, proy.saldo_actual] as [number, number] },
        ...proy.puntos.map((p) => ({ fecha: p.fecha, proyectado: p.saldo, rango: [p.inferior, p.superior] as [number, number] })),
      ]
    : [];
  const estado = !proy ? null : proy.saldo_proyectado < 0 ? "rojo" : proy.inferior < 0 ? "amarillo" : "verde";
  const mensual = (f?.mensual ?? []).map((m) => ({ ...m, salidas: m.compras + m.gastos }));

  return (
    <Pagina titulo="Flujo de efectivo"
      descripcion={f ? `Entradas por ventas y salidas por compras y gastos · ${f.periodo.etiqueta}.` : undefined}>
      {fl.error && <Aviso tipo="error">{fl.error}</Aviso>}
      {f ? (
        <div className="grid grid-kpi">
          <KpiCard indice={0} etiqueta="Efectivo al inicio" valor={f.saldo_inicial} formato={(n) => dinero(Math.round(n), false)} />
          <KpiCard indice={1} etiqueta="Entró por ventas" valor={f.entradas} formato={(n) => dinero(Math.round(n), false)} />
          <KpiCard indice={2} etiqueta="Salió" tecnico="Compras de mercancía + gastos del negocio" valor={f.compras + f.gastos}
            formato={(n) => dinero(Math.round(n), false)} nota={`compras ${dineroCompacto(f.compras)} · gastos ${dineroCompacto(f.gastos)}`} />
          <KpiCard indice={3} etiqueta="Efectivo al final" valor={f.saldo_final} formato={(n) => dinero(Math.round(n), false)}
            nota={f.periodo.etiqueta} />
        </div>
      ) : (
        <div className="grid grid-kpi">{[0, 1, 2, 3].map((i) => <TarjetaCargando key={i} alto={50} />)}</div>
      )}

      <Tarjeta retraso={0.05}>
        <TituloTarjeta icono={CalendarClock} titulo="Proyección a 30 días"
          sub={proy ? `Desde tu último dato (${fechaLarga(proy.fecha_corte)}), al ritmo de los últimos 30 días. No cambia con el periodo elegido arriba.` : "Calculando…"}
          derecha={estado && <Semaforo estado={estado} texto={estado === "rojo" ? "No alcanza" : estado === "amarillo" ? "Viene justo" : "Alcanza"} />} />
        {proy ? (
          <div className="grid grid-proy">
            <div className="pila">
              <Leyenda items={[{ nombre: "Efectivo real", color: SERIE.ventas, tipo: "linea" }, { nombre: "Proyección", color: SERIE.ventas, tipo: "punteada" },
                { nombre: "Rango probable", color: "color-mix(in srgb, var(--s1) 22%, transparent)" }]} />
              <div style={{ height: 270 }}>
                <ResponsiveContainer>
                  <ComposedChart data={datosProy} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--grid)" />
                    <XAxis dataKey="fecha" {...EJE} tickFormatter={fechaCorta} minTickGap={36} />
                    <YAxis {...EJE} width={64} tickFormatter={dineroCompacto} />
                    <ReferenceLine y={0} stroke="var(--bad)" strokeWidth={1} />
                    <ReferenceLine x={proy.fecha_corte} stroke="var(--axis)" label={{ value: "hoy", position: "insideTopRight", fill: "var(--muted)", fontSize: 11 }} />
                    <Tooltip content={<TooltipGrafica titulo={(l) => fechaCorta(String(l))} nombres={{ saldo: "Efectivo", proyectado: "Proyectado" }} />} />
                    <Area dataKey="rango" stroke="none" fill={SERIE.ventas} fillOpacity={0.14} isAnimationActive={false} name="Rango probable" />
                    <Line dataKey="saldo" stroke={SERIE.ventas} strokeWidth={2} dot={false} animationDuration={900} />
                    <Line dataKey="proyectado" stroke={SERIE.ventas} strokeWidth={2} strokeDasharray="6 4" dot={false} animationDuration={900} animationBegin={500} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
            <motion.div className="pila centrado" style={{ alignItems: "center", gap: 10 }} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.3 }}>
              <span className="eyebrow">En 30 días tendrías</span>
              <strong className="num" style={{ fontSize: "var(--fs-2xl)", color: proy.saldo_proyectado < 0 ? "var(--bad-ink)" : "var(--ink)" }}>
                {dinero(proy.saldo_proyectado)}
              </strong>
              <span className="pequeno muted">rango probable {dineroCompacto(proy.inferior)} a {dineroCompacto(proy.superior)}</span>
              <div className="fila" style={{ gap: 16, marginTop: 6 }}>
                <span className="pequeno fila" style={{ gap: 4 }}><ArrowDownLeft size={15} color="var(--s1)" /> entra {dinero(proy.entradas_diarias)}/día</span>
                <span className="pequeno fila" style={{ gap: 4 }}><ArrowUpRight size={15} color="var(--s2)" /> sale {dinero(proy.salidas_diarias)}/día</span>
              </div>
              {proy.saldo_proyectado < 0 && (
                <Aviso>
                  Pospón compras que no sean urgentes. Si lo necesitas, puedes evaluar un financiamiento de corto plazo para capital de
                  trabajo; compara costos y plazos antes de decidir. <em>Orientación general, no constituye asesoría financiera.</em>
                </Aviso>
              )}
            </motion.div>
          </div>
        ) : (
          <TarjetaCargando alto={240} />
        )}
      </Tarjeta>

      <div className="grid grid-2">
        <Tarjeta retraso={0.1}>
          <TituloTarjeta icono={ChartColumnBig} titulo="Entradas vs. salidas" sub={f?.periodo.etiqueta} />
          <Leyenda items={[{ nombre: "Entradas", color: SERIE.ventas }, { nombre: "Salidas", color: SERIE.gastos }]} />
          <div style={{ height: 250 }}>
            {f && (
              <ResponsiveContainer>
                <BarChart data={mensual} barGap={2} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="etiqueta" {...EJE} />
                  <YAxis {...EJE} width={60} tickFormatter={dineroCompacto} />
                  <Tooltip content={<TooltipGrafica nombres={{ entradas: "Entradas", salidas: "Salidas" }} />} cursor={{ fill: "var(--surface-hover)" }} />
                  <Bar dataKey="entradas" fill={SERIE.ventas} radius={[4, 4, 0, 0]} maxBarSize={28} animationDuration={800} />
                  <Bar dataKey="salidas" fill={SERIE.gastos} radius={[4, 4, 0, 0]} maxBarSize={28} animationDuration={800} animationBegin={150} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Tarjeta>
        <Tarjeta retraso={0.14}>
          <TituloTarjeta icono={Wallet} titulo="Salidas de efectivo por concepto" sub="Compras de mercancía y gastos del periodo" />
          {f && (
            <div className="pila" style={{ gap: 14 }}>
              {[
                { k: "Compras de mercancía", v: f.compras, c: SERIE.gastos, d: "Lo que pagaste a proveedores para resurtir." },
                { k: "Gastos del negocio", v: f.gastos, c: SERIE.s4, d: "Renta, sueldos, servicios, insumos…" },
              ].map((x, i) => {
                const total = f.compras + f.gastos || 1;
                return (
                  <div key={x.k} className="pila" style={{ gap: 6 }}>
                    <div className="fila-entre pequeno">
                      <span className="fila" style={{ gap: 8 }}>
                        <i style={{ width: 10, height: 10, borderRadius: 3, background: x.c, display: "inline-block" }} />
                        <strong style={{ fontWeight: 600 }}>{x.k}</strong>
                      </span>
                      <span className="num"><strong>{dinero(x.v)}</strong> <span className="muted">· {Math.round((x.v / total) * 100)}%</span></span>
                    </div>
                    <div className="barra"><motion.span style={{ background: x.c }} initial={{ width: 0 }} animate={{ width: `${(x.v / total) * 100}%` }}
                      transition={{ delay: 0.2 + i * 0.1, duration: 0.9, ease: [0.22, 1, 0.36, 1] }} /></div>
                    <span className="mini muted">{x.d}</span>
                  </div>
                );
              })}
              <p className="nota-pie mini">
                <Info size={12} aria-hidden="true" /> La proyección usa una línea base (promedio móvil de 30 días). En la siguiente
                fase se agregarán escenarios y temporadas.
              </p>
            </div>
          )}
        </Tarjeta>
      </div>
    </Pagina>
  );
}
