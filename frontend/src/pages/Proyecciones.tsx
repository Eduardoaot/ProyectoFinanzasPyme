import { motion } from "framer-motion";
import { Boxes, CalendarClock, Gauge, LineChart as IconoLinea, PiggyBank, SlidersHorizontal, Target, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Area, CartesianGrid, Cell, ComposedChart, Line, Pie, PieChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TarjetaAlerta } from "../components/AlertaTarjeta";
import { CATEGORICOS, EJE, Leyenda, SERIE, TooltipGrafica } from "../components/charts/comun";
import { Aviso, EstadoVacio, Segmentado, Semaforo, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { ClaraResumen } from "../components/ui/ClaraResumen";
import { KpiCard } from "../components/ui/KpiCard";
import { Pagina } from "../components/ui/Pagina";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import { dinero, dineroCompacto, fechaCorta, fechaLarga, numero, pct } from "../lib/formato";
import type { EscenarioEntrada, ParteReparto, Proyecciones as TipoProyecciones } from "../lib/predictivo";

const REPARTO: Record<ParteReparto["clave"], { texto: string; ayuda: string }> = {
  impuestos: { texto: "Impuestos (SAT)", ayuda: "Sepáralo apenas entre la venta." },
  deuda_obligatoria: { texto: "Pagos de deudas", ayuda: "Lo que te toca pagar este mes." },
  deuda_extra: { texto: "Abono extra a tu deuda más cara", ayuda: "Solo si tienes deudas con tasa mayor a 30% anual." },
  fondo_emergencia: { texto: "Fondo de emergencia", ayuda: "Tu colchón para imprevistos." },
  reinversion: { texto: "Reinversión", ayuda: "Inventario de los productos que más te dejan." },
  retiro: { texto: "Tu retiro", ayuda: "Lo que sobra para ti." },
};

const ESCENARIO_BASE: EscenarioEntrada = { ventas_pct: 0, precios_pct: 0, gasto_fijo_extra: 0, deuda_monto: 0, deuda_tasa: 0, deuda_plazo: 0 };

function Comparacion({ etiqueta, base, escenario, formato = (n: number) => dinero(Math.round(n), false), mejorSiSube = true }: {
  etiqueta: string; base: number | null; escenario: number | null; formato?: (n: number) => string; mejorSiSube?: boolean;
}) {
  const dif = base !== null && escenario !== null ? escenario - base : 0;
  const bien = Math.abs(dif) < 0.5 ? null : mejorSiSube ? dif > 0 : dif < 0;
  return (
    <div className="mini-kpi">
      <div className="k">{etiqueta}</div>
      <div className="v num">{escenario === null ? "—" : formato(escenario)}</div>
      <div className="mini num" style={{ color: bien === null ? "var(--muted)" : bien ? "var(--ok-ink)" : "var(--bad-ink)" }}>
        {bien === null ? "igual que hoy" : `${dif > 0 ? "+" : "−"}${formato(Math.abs(dif))} vs hoy`}
      </div>
    </div>
  );
}

function Escenarios({ idEmpresa, semanas, base }: { idEmpresa: number; semanas: number; base: TipoProyecciones }) {
  const [esc, setEsc] = useState<EscenarioEntrada>(ESCENARIO_BASE);
  const [res, setRes] = useState<TipoProyecciones | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cambiado = JSON.stringify(esc) !== JSON.stringify(ESCENARIO_BASE);

  useEffect(() => {
    if (!cambiado) {
      setRes(null);
      return;
    }
    const t = setTimeout(() => {
      api.post<TipoProyecciones>(`/empresas/${idEmpresa}/proyecciones/escenario?semanas=${semanas}`, esc)
        .then((r) => { setRes(r); setError(null); })
        .catch((e: Error) => setError(e.message));
    }, 350);
    return () => clearTimeout(t);
  }, [esc, idEmpresa, semanas, cambiado]);

  const ver = res ?? base;
  const poner = (k: keyof EscenarioEntrada, v: number) => setEsc((e) => ({ ...e, [k]: v }));
  return (
    <Tarjeta retraso={0.1}>
      <TituloTarjeta icono={SlidersHorizontal} titulo="¿Qué pasa si…?" sub="Mueve los controles y mira cómo cambia tu mes. No se guarda nada."
        derecha={cambiado && <button className="btn chico" onClick={() => setEsc(ESCENARIO_BASE)}>Regresar a hoy</button>} />
      <div className="grid grid-2">
        <div className="pila" style={{ gap: 16 }}>
          <div className="campo">
            <label htmlFor="esc-ventas">Si vendo {esc.ventas_pct > 0 ? "+" : ""}{Math.round(esc.ventas_pct * 100)}%</label>
            <input id="esc-ventas" type="range" min={-30} max={30} step={1} value={Math.round(esc.ventas_pct * 100)} onChange={(e) => poner("ventas_pct", Number(e.target.value) / 100)} />
          </div>
          <div className="campo">
            <label htmlFor="esc-precios">Si cambio mis precios {esc.precios_pct > 0 ? "+" : ""}{Math.round(esc.precios_pct * 100)}%</label>
            <input id="esc-precios" type="range" min={-10} max={10} step={1} value={Math.round(esc.precios_pct * 100)} onChange={(e) => poner("precios_pct", Number(e.target.value) / 100)} />
          </div>
          <div className="campo">
            <label htmlFor="esc-gasto">Nuevo gasto fijo al mes (por ejemplo, contratar a alguien)</label>
            <input id="esc-gasto" className="input" type="number" min={0} step={100} value={esc.gasto_fijo_extra || ""} placeholder="$0"
              onChange={(e) => poner("gasto_fijo_extra", Math.max(0, Number(e.target.value)))} />
          </div>
          <fieldset className="pila" style={{ border: 0, padding: 0, margin: 0, gap: 8 }}>
            <legend style={{ fontSize: "var(--fs-sm)", fontWeight: 600, color: "var(--ink-2)" }}>Si pido una nueva deuda</legend>
            <div className="grid" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
              <input className="input" type="number" min={0} step={1000} placeholder="Monto $" aria-label="Monto de la nueva deuda" value={esc.deuda_monto || ""}
                onChange={(e) => poner("deuda_monto", Math.max(0, Number(e.target.value)))} />
              <input className="input" type="number" min={0} max={500} step={1} placeholder="Tasa anual %" aria-label="Tasa anual en por ciento" value={esc.deuda_tasa ? Math.round(esc.deuda_tasa * 100) : ""}
                onChange={(e) => poner("deuda_tasa", Math.max(0, Number(e.target.value)) / 100)} />
              <input className="input" type="number" min={0} max={360} step={1} placeholder="Meses" aria-label="Plazo en meses" value={esc.deuda_plazo || ""}
                onChange={(e) => poner("deuda_plazo", Math.max(0, Math.round(Number(e.target.value))))} />
            </div>
          </fieldset>
          {error && <Aviso tipo="error">{error}</Aviso>}
        </div>
        <div className="mini-kpis" aria-live="polite">
          <Comparacion etiqueta="Lo que ganarías en el mes" base={base.mes.utilidad} escenario={ver.mes.utilidad} />
          <Comparacion etiqueta="Efectivo a fin de mes" base={base.flujo.fin_de_mes.esperado} escenario={ver.flujo.fin_de_mes.esperado} />
          <Comparacion etiqueta="Ventas mínimas para cubrir gastos" base={base.equilibrio.mensual} escenario={ver.equilibrio.mensual} mejorSiSube={false} />
          <div className="mini-kpi">
            <div className="k">Fecha de riesgo de efectivo</div>
            <div className="v num">{ver.flujo.fecha_riesgo ? fechaCorta(ver.flujo.fecha_riesgo) : "Sin riesgo"}</div>
            <div className="mini muted">{base.flujo.fecha_riesgo ? `hoy: ${fechaCorta(base.flujo.fecha_riesgo)}` : "hoy: sin riesgo"}</div>
          </div>
        </div>
      </div>
    </Tarjeta>
  );
}

export function Proyecciones() {
  const { empresa } = useSesion();
  const id = empresa?.id_empresa;
  const [semanas, setSemanas] = useState<"4" | "8" | "12">("8");
  const listo = Boolean(id && empresa?.tiene_datos);
  const pr = useApi<TipoProyecciones>(listo ? `/empresas/${id}/proyecciones` : null, { semanas });
  const d = pr.datos;

  const ventasGrafica = useMemo(
    () => (d?.pronostico.semanas ?? []).map((s) => ({ ...s, rango: s.pesimista !== null && s.optimista !== null ? ([s.pesimista, s.optimista] as [number, number]) : undefined })),
    [d],
  );
  const efectivoGrafica = useMemo(
    () => (d?.flujo.serie ?? []).slice(0, Number(semanas) * 7).map((p) => ({ ...p, rango: [p.pesimista, p.optimista] as [number, number] })),
    [d, semanas],
  );
  const puntoRiesgo = d?.flujo.fecha_riesgo ? d.flujo.serie.find((p) => p.fecha === d.flujo.fecha_riesgo) : undefined;
  const reparto = (d?.consejos.distribucion ?? []).filter((p) => p.asignado > 0);

  if (!listo) {
    return (
      <Pagina eyebrow="Proyecciones y consejos" titulo="¿Cómo te va a ir?">
        <EstadoVacio icono={TrendingUp} titulo="Aún no hay datos para proyectar" texto="Sube tu primer Excel de ventas para ver tus proyecciones." />
      </Pagina>
    );
  }

  return (
    <Pagina eyebrow="Proyecciones y consejos" titulo="¿Cómo te va a ir y qué haces?"
      descripcion="Estimamos tus ventas, tu efectivo y lo que deberías comprar y ahorrar. Son estimaciones calculadas con tu historial; mientras más datos tengas, más precisas."
      acciones={<Segmentado etiqueta="Horizonte del pronóstico" valor={semanas} onChange={setSemanas}
        opciones={[{ valor: "4", texto: "4 semanas" }, { valor: "8", texto: "8 semanas" }, { valor: "12", texto: "12 semanas" }]} />}>
      {pr.error && <Aviso tipo="error">{pr.error}</Aviso>}
      {d?.pronostico.pocos_datos && <Aviso>Pronóstico con pocos datos: usamos un promedio simple porque tienes menos de 8 semanas de historia.</Aviso>}

      {d ? (
        <div className="grid grid-kpi">
          <KpiCard indice={0} etiqueta={`Ventas de ${d.mes.etiqueta.split(" ")[0].toLowerCase()}`} tecnico="Ventas proyectadas del mes (real a la fecha + pronóstico)"
            valor={d.mes.ventas} formato={(n) => dinero(Math.round(n), false)} nota={`entre ${dineroCompacto(d.mes.ventas_pesimista)} y ${dineroCompacto(d.mes.ventas_optimista)}`} />
          <KpiCard indice={1} etiqueta="Lo que ganarías" tecnico="Utilidad proyectada del mes, antes de impuestos"
            valor={d.mes.utilidad} formato={(n) => dinero(Math.round(n), false)} nota={`entre ${dineroCompacto(d.mes.utilidad_pesimista)} y ${dineroCompacto(d.mes.utilidad_optimista)}`} />
          <KpiCard indice={2} etiqueta="Efectivo a fin de mes" tecnico="Efectivo estimado (escenario esperado)"
            valor={d.flujo.fin_de_mes.esperado} formato={(n) => dinero(Math.round(n), false)} nota={`si te va mal: ${dineroCompacto(d.flujo.fin_de_mes.pesimista)}`} />
          <KpiCard indice={3} etiqueta="Días de colchón" tecnico="Efectivo actual / gasto diario promedio (gastos + compras + pagos de deuda)"
            valor={d.flujo.dias_colchon} formato={(n) => `${numero(Math.round(n))} días`} nota="cuánto aguantas sin vender" />
          <KpiCard indice={4} etiqueta="Precisión aproximada" tecnico="100% menos el error promedio del método en las últimas 8 semanas"
            valor={d.pronostico.precision} formato={(n) => `${numero(Math.round(n))}%`} nota={d.pronostico.precision === null ? "faltan semanas de historia" : "qué tan bien acertó antes"} />
        </div>
      ) : (
        <div className="grid grid-kpi">{[0, 1, 2, 3, 4].map((i) => <TarjetaCargando key={i} alto={50} />)}</div>
      )}

      {d && d.alertas.length > 0 && (
        <div className="pila">
          {d.alertas.map((a, i) => <TarjetaAlerta key={a.id} alerta={a} indice={i} compacta />)}
        </div>
      )}

      <ClaraResumen ruta={id ? `/empresas/${id}/proyecciones/clara` : null} />

      <div className="grid grid-2">
        <Tarjeta retraso={0.04}>
          <TituloTarjeta icono={IconoLinea} titulo="Tus ventas por semana"
            sub={d ? `Próximas ${semanas} semanas: ${dinero(Math.round(d.pronostico.total_horizonte), false)} (entre ${dineroCompacto(d.pronostico.total_horizonte_pesimista)} y ${dineroCompacto(d.pronostico.total_horizonte_optimista)})` : "Calculando…"} />
          <Leyenda items={[{ nombre: "Vendido", color: SERIE.ventas, tipo: "linea" }, { nombre: "Pronóstico", color: SERIE.ventas, tipo: "punteada" },
            { nombre: "Si te va mal / bien", color: "color-mix(in srgb, var(--s1) 22%, transparent)" }]} />
          <div style={{ height: 280 }}>
            {d ? (
              <ResponsiveContainer>
                <ComposedChart data={ventasGrafica} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="fecha" {...EJE} tickFormatter={fechaCorta} minTickGap={36} />
                  <YAxis {...EJE} width={60} tickFormatter={dineroCompacto} />
                  <ReferenceLine x={ventasGrafica.find((s) => s.real !== null && s.pronostico !== null)?.fecha} stroke="var(--axis)" label={{ value: "hoy", position: "insideTopRight", fill: "var(--muted)", fontSize: 11 }} />
                  <Tooltip content={<TooltipGrafica titulo={(l) => `Semana del ${fechaCorta(String(l))}`} nombres={{ real: "Vendido", pronostico: "Pronóstico" }} />} />
                  <Area dataKey="rango" stroke="none" fill={SERIE.ventas} fillOpacity={0.15} isAnimationActive={false} name="_rango" />
                  <Line dataKey="real" stroke={SERIE.ventas} strokeWidth={2} dot={false} animationDuration={900} />
                  <Line dataKey="pronostico" stroke={SERIE.ventas} strokeWidth={2} strokeDasharray="6 4" dot={false} animationDuration={900} animationBegin={400} />
                </ComposedChart>
              </ResponsiveContainer>
            ) : <TarjetaCargando alto={240} />}
          </div>
        </Tarjeta>

        <Tarjeta retraso={0.08}>
          <TituloTarjeta icono={CalendarClock} titulo="Tu efectivo día por día"
            derecha={d && (d.flujo.fecha_riesgo ? <Semaforo estado="rojo" texto={`Riesgo el ${fechaCorta(d.flujo.fecha_riesgo)}`} /> : <Semaforo estado="verde" texto="Sin riesgo" />)}
            sub={d ? `Hoy tienes ${dinero(d.flujo.efectivo_actual, false)}. Tu mínimo de seguridad es ${dinero(d.flujo.minimo_seguridad, false)}.` : "Calculando…"} />
          <Leyenda items={[{ nombre: "Esperado", color: SERIE.utilidad, tipo: "linea" }, { nombre: "Si te va mal / bien", color: "color-mix(in srgb, var(--s3) 22%, transparent)" },
            { nombre: "Mínimo de seguridad", color: "var(--bad)", tipo: "punteada" }]} />
          <div style={{ height: 280 }}>
            {d ? (
              <ResponsiveContainer>
                <ComposedChart data={efectivoGrafica} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="fecha" {...EJE} tickFormatter={fechaCorta} minTickGap={36} />
                  <YAxis {...EJE} width={60} tickFormatter={dineroCompacto} domain={["auto", "auto"]} />
                  <ReferenceLine y={d.flujo.minimo_seguridad} stroke="var(--bad)" strokeDasharray="5 4" label={{ value: "mínimo", position: "insideBottomRight", fill: "var(--bad-ink)", fontSize: 11 }} />
                  {puntoRiesgo && <ReferenceDot x={puntoRiesgo.fecha} y={puntoRiesgo.pesimista} r={6} fill="var(--bad)" stroke="var(--surface)" strokeWidth={2} />}
                  <Tooltip content={<TooltipGrafica titulo={(l) => fechaLarga(String(l))} nombres={{ esperado: "Esperado" }} />} />
                  <Area dataKey="rango" stroke="none" fill={SERIE.utilidad} fillOpacity={0.15} isAnimationActive={false} name="_rango" />
                  <Line dataKey="esperado" stroke={SERIE.utilidad} strokeWidth={2} dot={false} animationDuration={900} />
                </ComposedChart>
              </ResponsiveContainer>
            ) : <TarjetaCargando alto={240} />}
          </div>
          {d?.flujo.fecha_riesgo && d.flujo.causa_riesgo && (
            <Aviso>El {fechaLarga(d.flujo.fecha_riesgo)}, si te va mal, tu efectivo bajaría de tu mínimo por {d.flujo.causa_riesgo.concepto} ({dinero(d.flujo.causa_riesgo.monto, false)}).</Aviso>
          )}
        </Tarjeta>
      </div>

      {d && (
        <Tarjeta retraso={0.12}>
          <TituloTarjeta icono={Target} titulo="¿Ya cubriste tus gastos este mes?" sub={`Ventas mínimas al mes para no perder: ${d.equilibrio.mensual === null ? "—" : dinero(Math.round(d.equilibrio.mensual), false)} (≈ ${d.equilibrio.diario === null ? "—" : dinero(Math.round(d.equilibrio.diario), false)} al día)`} />
          <div className="medidor" role="img" aria-label={`Avance ${pct(d.equilibrio.avance, 0)}`}>
            <motion.div className="relleno" initial={{ width: 0 }} animate={{ width: `${Math.round(d.equilibrio.avance * 100)}%` }} transition={{ duration: 0.9 }} />
          </div>
          <div className="fila-entre envolver">
            <strong>
              {d.equilibrio.dia_cubierto ? `Este mes cubres tus gastos el ${fechaLarga(d.equilibrio.dia_cubierto)}.` : `Te faltan ${dinero(d.equilibrio.faltante, false)} de utilidad bruta para cubrir tus gastos.`}
            </strong>
            <span className="muted pequeno">
              Margen de seguridad: {d.equilibrio.margen_seguridad === null ? "—" : pct(d.equilibrio.margen_seguridad, 0)} (qué tanto pueden bajar tus ventas antes de perder)
            </span>
          </div>
        </Tarjeta>
      )}

      {d && (
        <Tarjeta retraso={0.14}>
          <TituloTarjeta icono={Boxes} titulo="¿Cuánto debo comprar?" sub={`Compra sugerida: ${dinero(d.inventario.total_compra_sugerida, false)} · Puedes gastar hasta ${dinero(d.inventario.presupuesto, false)} sin bajar de tu mínimo`}
            derecha={d.inventario.alcanza ? <Semaforo estado="verde" texto="Te alcanza" /> : <Semaforo estado="amarillo" texto="Pospón algunos" />} />
          {!d.inventario.alcanza && (
            <Aviso>Tu efectivo no alcanza para todo. Comprarías primero lo que más te deja y pospondrías: {d.inventario.pospuestos.join(", ")}.</Aviso>
          )}
          {d.inventario.monto_excesivo > 0 && (
            <Aviso>Tienes {dinero(d.inventario.monto_excesivo, false)} detenidos en productos con más de 60 días de inventario. Evita comprarlos por ahora.</Aviso>
          )}
          <div className="tabla-envoltura">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Producto</th><th className="der">Tienes</th><th className="der">Te dura</th><th className="der">Se acaba</th>
                  <th className="der" title="Cuando bajes de esta cantidad, ya toca pedir">Pide al llegar a</th><th className="der">Compra</th><th className="der">Cuesta</th>
                </tr>
              </thead>
              <tbody>
                {d.inventario.productos.slice(0, 40).map((p) => (
                  <tr key={p.id_producto}>
                    <td><Semaforo estado={p.semaforo} texto={p.nombre} />{p.excesivo && <span className="chip" style={{ marginLeft: 6 }}>mucho inventario</span>}</td>
                    <td className="der num">{numero(p.existencias)} {p.unidad}</td>
                    <td className="der num">{p.cobertura_dias === null ? "sin ventas" : `${numero(Math.round(p.cobertura_dias))} días`}</td>
                    <td className="der num muted">{p.fecha_agotamiento ? fechaCorta(p.fecha_agotamiento) : "—"}</td>
                    <td className="der num muted">{numero(Math.ceil(p.punto_reorden))}</td>
                    <td className="der num"><strong>{p.cantidad_sugerida > 0 ? `${numero(p.cantidad_sugerida)} ${p.unidad}` : "—"}</strong>{p.posponer && <span className="chip" style={{ marginLeft: 6 }}>pospón</span>}</td>
                    <td className="der num">{p.cantidad_sugerida > 0 ? dinero(p.costo_compra, false) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mini muted justificado">
            Rojo: se acaba antes de que llegue tu pedido. Amarillo: ya toca pedir. Calculamos con tus ventas de las últimas 4 semanas, 95% de nivel de servicio y días de entrega de tu proveedor (3 si no lo has indicado).
          </p>
        </Tarjeta>
      )}

      {d && (
        <div className="grid grid-2">
          <Tarjeta retraso={0.16}>
            <TituloTarjeta icono={PiggyBank} titulo="¿Qué hago con lo que gano?" sub={`Utilidad proyectada de ${d.mes.etiqueta.split(" ")[0].toLowerCase()}: ${dinero(d.consejos.utilidad_proyectada, false)}`} />
            {d.consejos.faltante_obligatorio > 0 && (
              <Aviso tipo="error">Tu utilidad proyectada no alcanza para impuestos y pagos de deuda: te faltan {dinero(d.consejos.faltante_obligatorio, false)}.</Aviso>
            )}
            <div className="grid" style={{ gridTemplateColumns: "minmax(0, 190px) minmax(0, 1fr)", alignItems: "center" }}>
              <div style={{ height: 190 }} role="img" aria-label="Distribución sugerida de tu utilidad">
                {reparto.length > 0 ? (
                  <ResponsiveContainer>
                    <PieChart>
                      <Tooltip content={<TooltipGrafica formato={(v) => dinero(v, false)} />} />
                      <Pie data={reparto.map((p) => ({ name: REPARTO[p.clave].texto, value: p.asignado, dataKey: "value" }))} dataKey="value" innerRadius={52} outerRadius={84} paddingAngle={2} animationDuration={900}>
                        {reparto.map((p, i) => <Cell key={p.clave} fill={CATEGORICOS[i % CATEGORICOS.length]} stroke="var(--surface)" />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                ) : <p className="muted pequeno">Este mes no hay utilidad que repartir.</p>}
              </div>
              <ul className="pila" style={{ listStyle: "none", margin: 0, padding: 0, gap: 8 }}>
                {d.consejos.distribucion.map((p, i) => {
                  const k = reparto.findIndex((r) => r.clave === p.clave);
                  return (
                    <li key={p.clave} className="fila-entre pequeno">
                      <span className="fila" style={{ gap: 8 }} title={REPARTO[p.clave].ayuda}>
                        <i style={{ width: 10, height: 10, borderRadius: 3, background: k >= 0 ? CATEGORICOS[k % CATEGORICOS.length] : "var(--line)", display: "inline-block" }} />
                        {i + 1}. {REPARTO[p.clave].texto}
                      </span>
                      <strong className="num">{dinero(p.asignado, false)}</strong>
                    </li>
                  );
                })}
              </ul>
            </div>
            <p className="mini muted justificado">Orden de prioridad: primero impuestos y deudas, luego tu fondo, luego reinversión y al final tu retiro. Orientación general, no constituye asesoría financiera.</p>
          </Tarjeta>

          <Tarjeta retraso={0.2}>
            <TituloTarjeta icono={Gauge} titulo="¿Cuánto debo ahorrar?" />
            <div className="pila" style={{ gap: 16 }}>
              <div className="dato"><span className="k">Aparta para impuestos este mes</span><span className="v num">{dinero(d.consejos.apartado_impuestos, false)}</span></div>
              <div className="dato"><span className="k">Reserva para inventario (compra sugerida)</span><span className="v num">{dinero(d.consejos.reserva_inventario, false)}</span></div>
              <div className="pila" style={{ gap: 6 }}>
                <div className="fila-entre pequeno">
                  <strong>Fondo de emergencia</strong>
                  <span className="num muted">{dinero(d.consejos.fondo_emergencia.actual, false)} de {dinero(d.consejos.fondo_emergencia.meta, false)}</span>
                </div>
                <div className="barra" role="progressbar" aria-valuenow={Math.round(d.consejos.fondo_emergencia.avance * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Avance del fondo de emergencia">
                  <span style={{ width: `${Math.round(d.consejos.fondo_emergencia.avance * 100)}%` }} />
                </div>
                <span className="mini muted">Meta: 3 meses de gastos fijos y pagos de deuda. Para llegar en 6 meses, ahorra {dinero(d.consejos.fondo_emergencia.ahorro_mensual_6_meses, false)} al mes.</span>
              </div>
            </div>
          </Tarjeta>
        </div>
      )}

      {d && id && <Escenarios idEmpresa={id} semanas={Number(semanas)} base={d} />}
    </Pagina>
  );
}
