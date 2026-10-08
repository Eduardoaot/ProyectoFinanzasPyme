import { motion } from "framer-motion";
import { CalendarDays, ChartColumnBig, CircleCheck, CircleX, Landmark, Scale, Settings2, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EJE, Leyenda, SERIE, TooltipGrafica } from "../components/charts/comun";
import { Aviso, EstadoVacio, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { ClaraResumen } from "../components/ui/ClaraResumen";
import { KpiCard } from "../components/ui/KpiCard";
import { Pagina } from "../components/ui/Pagina";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import { dinero, dineroCompacto, fechaCorta, fechaLarga } from "../lib/formato";
import type { GastoClasificado, Impuestos as TipoImpuestos } from "../lib/predictivo";

const REGIMENES = {
  fisica: [
    { v: "626", t: "RESICO (626) · ingresos hasta $3.5 millones al año" },
    { v: "612", t: "Actividades Empresariales (612) · puedes deducir gastos" },
  ],
  moral: [{ v: "601", t: "General de Ley (601) · persona moral" }],
} as const;

function Configuracion({ idEmpresa, datos, alGuardar, editable }: { idEmpresa: number; datos: TipoImpuestos; alGuardar: () => void; editable: boolean }) {
  const c = datos.configuracion;
  const [tipo, setTipo] = useState(c.tipo_persona);
  const [regimen, setRegimen] = useState(c.regimen);
  const [morales, setMorales] = useState(c.factura_a_morales);
  const [pctMorales, setPctMorales] = useState(Math.round(c.pct_ventas_morales * 100));
  const [trabajadores, setTrabajadores] = useState(c.tiene_trabajadores);
  const [coef, setCoef] = useState(c.coeficiente_utilidad);
  const [estado, setEstado] = useState<"" | "guardando" | "listo" | string>("");

  useEffect(() => {
    setTipo(c.tipo_persona); setRegimen(c.regimen); setMorales(c.factura_a_morales); setPctMorales(Math.round(c.pct_ventas_morales * 100));
    setTrabajadores(c.tiene_trabajadores); setCoef(c.coeficiente_utilidad);
  }, [c]);

  const guardar = async () => {
    setEstado("guardando");
    try {
      await api.put(`/empresas/${idEmpresa}/impuestos/configuracion`, {
        tipo_persona: tipo, regimen, factura_a_morales: morales, pct_ventas_morales: pctMorales / 100, tiene_trabajadores: trabajadores, coeficiente_utilidad: coef,
      });
      setEstado("listo");
      alGuardar();
    } catch (e) {
      setEstado((e as Error).message);
    }
  };

  return (
    <Tarjeta retraso={0.04}>
      <TituloTarjeta icono={Settings2} titulo="Tu configuración fiscal" sub={`Hoy: ${c.regimen_nombre}`} />
      <div className="grid grid-2">
        <div className="campo">
          <label htmlFor="tipo-persona">Tipo de persona</label>
          <select id="tipo-persona" className="select" value={tipo} disabled={!editable}
            onChange={(e) => { const t = e.target.value as "fisica" | "moral"; setTipo(t); setRegimen(t === "moral" ? "601" : regimen === "601" ? "626" : regimen); }}>
            <option value="fisica">Persona física</option>
            <option value="moral">Persona moral (empresa)</option>
          </select>
        </div>
        <div className="campo">
          <label htmlFor="regimen">Régimen</label>
          <select id="regimen" className="select" value={regimen} disabled={!editable} onChange={(e) => setRegimen(e.target.value as "626" | "612" | "601")}>
            {REGIMENES[tipo].map((r) => <option key={r.v} value={r.v}>{r.t}</option>)}
          </select>
        </div>
        <label className="fila" style={{ gap: 8 }}>
          <input type="checkbox" checked={morales} disabled={!editable} onChange={(e) => setMorales(e.target.checked)} />
          <span>Le facturo a personas morales (empresas) <span className="muted">· te retienen 1.25% en RESICO</span></span>
        </label>
        {morales && (
          <div className="campo">
            <label htmlFor="pct-morales">¿Qué porcentaje de tus ventas es a empresas?</label>
            <input id="pct-morales" className="input" type="number" min={0} max={100} value={pctMorales} disabled={!editable} onChange={(e) => setPctMorales(Math.min(100, Math.max(0, Number(e.target.value))))} />
          </div>
        )}
        <label className="fila" style={{ gap: 8 }}>
          <input type="checkbox" checked={trabajadores} disabled={!editable} onChange={(e) => setTrabajadores(e.target.checked)} />
          <span>Tengo trabajadores <span className="muted">· calculamos el reparto de utilidades (PTU)</span></span>
        </label>
        {tipo === "moral" && (
          <div className="campo">
            <label htmlFor="coef">Coeficiente de utilidad del año anterior</label>
            <input id="coef" className="input" type="number" min={0} max={1} step={0.01} value={coef} disabled={!editable} onChange={(e) => setCoef(Number(e.target.value))} />
          </div>
        )}
      </div>
      <p className="mini muted justificado">La tasa de IVA (0% o 16%) de cada producto se sugiere según su categoría; puedes corregirla producto por producto.</p>
      <div className="fila">
        <button className="btn primario" onClick={guardar} disabled={!editable || estado === "guardando"}>Guardar configuración</button>
        {estado === "listo" && <span className="chip ok">Guardado</span>}
        {estado && estado !== "listo" && estado !== "guardando" && <span className="chip" role="alert">{estado}</span>}
        {!editable && <span className="muted pequeno">Tienes acceso de solo lectura.</span>}
      </div>
    </Tarjeta>
  );
}

const ESTADO = {
  deducible: { Icono: CircleCheck, texto: "Se deduce", color: "var(--ok-ink)" },
  parcial: { Icono: TriangleAlert, texto: "Se deduce en parte", color: "var(--warn-ink)" },
  no_deducible: { Icono: CircleX, texto: "No se deduce", color: "var(--bad-ink)" },
} as const;

function Deducciones({ idEmpresa, mes, editable, version, alCambiar }: { idEmpresa: number; mes: string; editable: boolean; version: number; alCambiar: () => void }) {
  const gastos = useApi<GastoClasificado[]>(`/empresas/${idEmpresa}/impuestos/gastos`, { mes, v: version });
  const [error, setError] = useState<string | null>(null);
  const cambiar = async (g: GastoClasificado, campos: Partial<Pick<GastoClasificado, "tiene_cfdi" | "medio_pago" | "uso">>) => {
    try {
      await api.patch(`/empresas/${idEmpresa}/gastos/${g.id_gasto}/fiscal`, campos);
      setError(null);
      gastos.recargar();
      alCambiar();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const lista = gastos.datos ?? [];
  return (
    <Tarjeta retraso={0.2}>
      <TituloTarjeta icono={CircleCheck} titulo="¿Esto se puede deducir?" sub="Cada gasto del mes con su factura, su forma de pago y el motivo" />
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!gastos.datos ? <TarjetaCargando alto={200} /> : lista.length === 0 ? <p className="muted">Este mes no hay gastos registrados.</p> : (
        <div className="tabla-envoltura">
          <table className="tabla">
            <thead>
              <tr><th>Gasto</th><th className="der">Monto</th><th>¿Tiene factura?</th><th>Forma de pago</th><th>Resultado</th></tr>
            </thead>
            <tbody>
              {lista.map((g) => {
                const { Icono, texto, color } = ESTADO[g.estado];
                return (
                  <tr key={g.id_gasto}>
                    <td><strong>{g.concepto}</strong><div className="mini muted">{fechaCorta(g.fecha)} · {g.categoria}</div></td>
                    <td className="der num">{dinero(g.monto)}</td>
                    <td>
                      <label className="fila" style={{ gap: 6 }}>
                        <input type="checkbox" checked={g.tiene_cfdi} disabled={!editable} onChange={(e) => cambiar(g, { tiene_cfdi: e.target.checked })} aria-label={`Tiene factura: ${g.concepto}`} />
                        <span className="pequeno">{g.tiene_cfdi ? "Sí" : "No"}</span>
                      </label>
                    </td>
                    <td>
                      <select className="select" style={{ height: 34 }} value={g.medio_pago} disabled={!editable} aria-label={`Forma de pago: ${g.concepto}`}
                        onChange={(e) => cambiar(g, { medio_pago: e.target.value as GastoClasificado["medio_pago"] })}>
                        <option value="efectivo">Efectivo</option><option value="transferencia">Transferencia</option>
                        <option value="tarjeta">Tarjeta</option><option value="cheque">Cheque</option>
                      </select>
                    </td>
                    <td>
                      <span className="fila" style={{ gap: 6, color }}><Icono size={15} aria-hidden="true" /><strong className="pequeno">{texto}</strong></span>
                      <div className="mini muted justificado" style={{ maxWidth: 320 }}>{g.motivo}</div>
                      {g.corregible && <div className="mini" style={{ color: "var(--celeste-strong)" }}>Si lo corriges, lo recuperas.</div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Tarjeta>
  );
}

export function Impuestos() {
  const { empresa, empresas } = useSesion();
  const id = empresa?.id_empresa;
  const editable = empresas.find((e) => e.id_empresa === id)?.rol !== "consulta";
  const [mes, setMes] = useState<string>("");
  const [version, setVersion] = useState(0);
  const listo = Boolean(id && empresa?.tiene_datos);
  const imp = useApi<TipoImpuestos>(listo ? `/empresas/${id}/impuestos` : null, { mes: mes || undefined, v: version });
  const d = imp.datos;
  const refrescar = () => { setVersion((v) => v + 1); imp.recargar(); };

  if (!listo) {
    return (
      <Pagina eyebrow="Impuestos" titulo="¿Cuánto debes pagar al SAT?">
        <EstadoVacio icono={Landmark} titulo="Aún no hay datos para calcular" texto="Sube tus ventas, compras y gastos para estimar tus impuestos del mes." />
      </Pagina>
    );
  }

  const ultimoMes = d && empresa?.ultimo_dato?.slice(0, 4) === d.mes.slice(0, 4) ? Number(empresa.ultimo_dato.slice(5, 7)) : 12;
  const barras = (d?.meses ?? []).map((m) => ({ etiqueta: m.etiqueta.split(" ")[0].slice(0, 3), isr: m.isr, iva: m.iva_a_pagar, favor: m.saldo_a_favor }));
  const perdido = d?.perdido_por_no_deducir;
  return (
    <Pagina eyebrow="Impuestos" titulo="¿Cuánto debes pagar al SAT este mes?"
      descripcion="Calculamos tu ISR y tu IVA con tus ventas cobradas, tus compras y tus gastos. Es una estimación para que apartes el dinero a tiempo."
      acciones={d && (
        <div className="fila">
          <label className="sr-only" htmlFor="mes-impuestos">Mes</label>
          <select id="mes-impuestos" className="select" value={mes || d.mes} onChange={(e) => setMes(e.target.value)}>
            {Array.from({ length: ultimoMes }, (_, i) => `${d.mes.slice(0, 4)}-${String(i + 1).padStart(2, "0")}`).reverse().map((m) => (
              <option key={m} value={m}>{new Date(`${m}-15T12:00:00`).toLocaleDateString("es-MX", { month: "long", year: "numeric" })}</option>
            ))}
          </select>
        </div>
      )}>
      {imp.error && <Aviso tipo="error">{imp.error}</Aviso>}
      <Aviso>{d?.aviso_legal ?? "Estimación informativa calculada con tus datos. No sustituye la declaración ni la asesoría de un contador. Verifica tasas y tarifas vigentes con el SAT."}</Aviso>

      {d ? (
        <div className="grid grid-kpi">
          <KpiCard indice={0} etiqueta="Pagas al SAT" tecnico="ISR + IVA del mes" valor={d.total_a_pagar} formato={(n) => dinero(n)} nota={`antes del ${fechaLarga(d.fecha_limite)}`} />
          <KpiCard indice={1} etiqueta="Aparta por cada $100" tecnico="Impuestos estimados / ventas × 100" valor={d.apartar_por_cada_100} formato={(n) => dinero(n)} nota="cada que vendes $100" />
          <KpiCard indice={2} etiqueta="ISR del mes" tecnico="Impuesto sobre la renta (sobre tu ganancia o tus ingresos)" valor={d.isr} formato={(n) => dinero(n)} />
          <KpiCard indice={3} etiqueta={d.saldo_a_favor > 0 ? "IVA a tu favor" : "IVA del mes"} tecnico="IVA trasladado − IVA acreditable" valor={d.saldo_a_favor > 0 ? d.saldo_a_favor : d.iva_a_pagar} formato={(n) => dinero(n)}
            nota={d.saldo_a_favor > 0 ? "se descuenta en los meses siguientes" : undefined} />
          <KpiCard indice={4} etiqueta="Tasa de impuestos del año" tecnico="(ISR + IVA pagados) / ingresos del año" valor={d.tasa_efectiva_anual === null ? null : d.tasa_efectiva_anual * 100} formato={(n) => `${n.toFixed(1)}%`} />
          <KpiCard indice={5} etiqueta="Dinero que estás perdiendo" tecnico="Gastos sin factura o en efectivo × tasa marginal + IVA no acreditado" valor={perdido?.monto ?? 0} formato={(n) => dinero(n)}
            nota={perdido && perdido.gastos > 0 ? `por ${perdido.gastos} gastos sin deducir` : "estás al corriente"} />
        </div>
      ) : (
        <div className="grid grid-kpi">{[0, 1, 2, 3, 4, 5].map((i) => <TarjetaCargando key={i} alto={50} />)}</div>
      )}

      {d?.mensaje_resico && <Aviso>{d.mensaje_resico}</Aviso>}
      {d?.explicacion_iva && <Aviso>{d.explicacion_iva}</Aviso>}
      {d?.limite_resico && d.limite_resico.estado !== "ok" && (
        <Aviso tipo={d.limite_resico.estado === "excedido" ? "error" : "info"}>
          {d.limite_resico.estado === "excedido" ? "Superaste" : "Te acercas a"} el límite de {dinero(d.limite_resico.limite, false)} de ingresos al año para seguir en RESICO: llevas {dinero(d.limite_resico.ingresos_acumulados, false)}.
        </Aviso>
      )}
      {perdido && perdido.gastos > 0 && (
        <Aviso>
          {dinero(perdido.sin_cfdi, false)} de tus gastos no tienen factura y {dinero(perdido.efectivo, false)} se pagaron en efectivo de forma que no se deduce. Pide siempre factura a nombre de tu negocio y paga con transferencia o tarjeta.
        </Aviso>
      )}

      <ClaraResumen ruta={id ? `/empresas/${id}/impuestos/clara` : null} version={`${version}-${d?.mes ?? ""}`} />

      <div className="grid grid-2">
        <Tarjeta retraso={0.06}>
          <TituloTarjeta icono={ChartColumnBig} titulo="Mes por mes" sub={`Acumulado del año: ${d ? dinero(d.total_acumulado_anio, false) : "—"}`} />
          <Leyenda items={[{ nombre: "ISR", color: SERIE.ventas }, { nombre: "IVA a pagar", color: SERIE.gastos }, { nombre: "IVA a favor", color: SERIE.utilidad }]} />
          <div style={{ height: 250 }}>
            {d ? (
              <ResponsiveContainer>
                <BarChart data={barras} barGap={2} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="etiqueta" {...EJE} />
                  <YAxis {...EJE} width={56} tickFormatter={dineroCompacto} />
                  <Tooltip content={<TooltipGrafica nombres={{ isr: "ISR", iva: "IVA a pagar", favor: "IVA a favor" }} />} cursor={{ fill: "var(--surface-hover)" }} />
                  <Bar dataKey="isr" fill={SERIE.ventas} radius={[4, 4, 0, 0]} maxBarSize={22} activeBar={{ stroke: "none", fillOpacity: 0.85 }} />
                  <Bar dataKey="iva" fill={SERIE.gastos} radius={[4, 4, 0, 0]} maxBarSize={22} activeBar={{ stroke: "none", fillOpacity: 0.85 }} />
                  <Bar dataKey="favor" fill={SERIE.utilidad} radius={[4, 4, 0, 0]} maxBarSize={22} activeBar={{ stroke: "none", fillOpacity: 0.85 }} />
                </BarChart>
              </ResponsiveContainer>
            ) : <TarjetaCargando alto={220} />}
          </div>
        </Tarjeta>

        <Tarjeta retraso={0.1}>
          <TituloTarjeta icono={CalendarDays} titulo="Calendario fiscal" sub="Próximas fechas y cuánto apartar" />
          <ul className="pila" style={{ listStyle: "none", margin: 0, padding: 0, gap: 10 }}>
            {(d?.calendario ?? []).map((c) => (
              <motion.li key={c.fecha + c.concepto} className="dato" initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}>
                <span className="k"><strong style={{ color: "var(--ink)" }}>{fechaLarga(c.fecha)}</strong><br /><span className="mini">{c.concepto}</span></span>
                <span className="v num">{c.monto === null ? "—" : dinero(c.monto, false)}{c.estimado && c.monto !== null && <span className="mini muted"> est.</span>}</span>
              </motion.li>
            ))}
          </ul>
          {d?.ptu && <p className="mini muted justificado">PTU: estimamos {dinero(d.ptu.anual_estimada, false)} al año; aparta {dinero(d.ptu.provision_mensual, false)} cada mes.</p>}
        </Tarjeta>
      </div>

      {d?.comparador_regimen && (
        <Tarjeta retraso={0.14}>
          <TituloTarjeta icono={Scale} titulo="¿Te conviene RESICO o Actividades Empresariales?" sub="ISR anual estimado con tus datos reales del año" />
          <div className="grid grid-2">
            {([
              ["resico", "RESICO", d.comparador_regimen.resico_anual, "No deduce gastos, pero la tasa es de 1% a 2.5% de tus ingresos."],
              ["actividades_empresariales", "Actividades Empresariales", d.comparador_regimen.actividades_empresariales_anual, "Deduces tus compras y gastos, y pagas según la tarifa progresiva."],
            ] as const).map(([clave, nombre, monto, nota]) => (
              <div key={clave} className="mini-kpi" style={{ outline: d.comparador_regimen?.conviene === clave ? "2px solid var(--ok)" : undefined }}>
                <div className="k">{nombre} {d.comparador_regimen?.actual === clave && <span className="chip">tu régimen</span>} {d.comparador_regimen?.conviene === clave && <span className="chip ok">te conviene</span>}</div>
                <div className="v num">{dinero(monto, false)} <span className="mini muted">al año</span></div>
                <div className="mini muted">{nota}</div>
              </div>
            ))}
          </div>
          <p className="mini muted justificado">
            {d.comparador_regimen.conviene === d.comparador_regimen.actual
              ? `Con tus datos, tu régimen actual es el más barato (diferencia de ${dinero(d.comparador_regimen.ahorro, false)} al año).`
              : `Con tus datos, cambiar te ahorraría unos ${dinero(d.comparador_regimen.ahorro, false)} al año. Platícalo con tu contador antes de decidir.`}
            {!d.comparador_regimen.elegible_resico && " Tus ingresos anualizados superan el límite para estar en RESICO."} {d.comparador_regimen.nota}
          </p>
        </Tarjeta>
      )}

      {d && id && <Configuracion idEmpresa={id} datos={d} alGuardar={refrescar} editable={editable} />}
      {d && id && <Deducciones idEmpresa={id} mes={mes || d.mes} editable={editable} version={version} alCambiar={() => setVersion((v) => v + 1)} />}
      <p className="mini muted justificado">{d?.aviso_legal}</p>
    </Pagina>
  );
}
