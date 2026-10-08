import { AnimatePresence, motion } from "framer-motion";
import { Banknote, CalendarClock, CreditCard, Flag, Pencil, Plus, Scale, Trash2, TrendingDown, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TarjetaAlerta } from "../components/AlertaTarjeta";
import { EJE, Leyenda, SERIE, TooltipGrafica } from "../components/charts/comun";
import { Aviso, EstadoVacio, Semaforo, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { ClaraResumen } from "../components/ui/ClaraResumen";
import { KpiCard } from "../components/ui/KpiCard";
import { Pagina } from "../components/ui/Pagina";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import { dinero, dineroCompacto, fechaCorta, fechaLarga, numero, pct } from "../lib/formato";
import type { Deuda, PanelDeudas, TipoDeuda } from "../lib/predictivo";

const TIPOS: { v: TipoDeuda; t: string }[] = [
  { v: "tarjeta_credito", t: "Tarjeta de crédito" }, { v: "credito_simple", t: "Crédito simple" }, { v: "credito_revolvente", t: "Crédito revolvente" },
  { v: "proveedor", t: "Deuda con proveedor" }, { v: "prestamo_personal", t: "Préstamo personal / familiar" }, { v: "arrendamiento", t: "Arrendamiento" },
];

interface Formulario {
  acreedor: string; tipo: TipoDeuda; monto_original: string; saldo_actual: string; tasa: string; cat: string; plazo_meses: string; pago_mensual: string;
  limite_credito: string; fecha_inicio: string; dia_corte: string; dia_limite_pago: string; comisiones_mensuales: string; tasa_moratoria: string;
  aplica_iva_intereses: boolean; uso: "negocio" | "personal";
}

const VACIO: Formulario = {
  acreedor: "", tipo: "credito_simple", monto_original: "", saldo_actual: "", tasa: "", cat: "", plazo_meses: "", pago_mensual: "", limite_credito: "",
  fecha_inicio: new Date().toISOString().slice(0, 10), dia_corte: "", dia_limite_pago: "", comisiones_mensuales: "", tasa_moratoria: "", aplica_iva_intereses: true, uso: "negocio",
};

const num = (v: string): number | null => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Number(v));

function desde(d: Deuda): Formulario {
  const s = (n: number | null) => (n === null ? "" : String(n));
  return {
    acreedor: d.acreedor, tipo: d.tipo, monto_original: s(d.monto_original), saldo_actual: s(d.saldo_actual), tasa: s(Math.round(d.tasa_interes_anual * 10000) / 100),
    cat: s(d.cat === null ? null : Math.round(d.cat * 10000) / 100), plazo_meses: s(d.plazo_meses), pago_mensual: s(d.pago_mensual_capturado), limite_credito: s(d.limite_credito),
    fecha_inicio: d.fecha_inicio, dia_corte: s(d.dia_corte), dia_limite_pago: s(d.dia_limite_pago), comisiones_mensuales: s(d.comisiones_mensuales || null),
    tasa_moratoria: s(d.tasa_moratoria_anual === null ? null : Math.round(d.tasa_moratoria_anual * 10000) / 100), aplica_iva_intereses: d.aplica_iva_intereses, uso: d.uso,
  };
}

function Cajon({ editando, alCerrar, alGuardar }: { editando: Deuda | null; alCerrar: () => void; alGuardar: (f: Formulario) => Promise<void> }) {
  const [f, setF] = useState<Formulario>(editando ? desde(editando) : VACIO);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const poner = <K extends keyof Formulario>(k: K, v: Formulario[K]) => setF((x) => ({ ...x, [k]: v }));
  const revolvente = f.tipo === "tarjeta_credito" || f.tipo === "credito_revolvente";
  const campo = (id: keyof Formulario, etiqueta: string, tipo = "number", extra: object = {}) => (
    <div className="campo">
      <label htmlFor={`d-${id}`}>{etiqueta}</label>
      <input id={`d-${id}`} className="input" type={tipo} value={String(f[id])} onChange={(e) => poner(id, e.target.value as never)} {...extra} />
    </div>
  );
  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await alGuardar(f);
    } catch (err) {
      setError((err as Error).message);
      setEnviando(false);
    }
  };
  return (
    <>
      <motion.div className="velo" style={{ zIndex: 65 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={alCerrar} />
      <motion.aside className="cajon" role="dialog" aria-label={editando ? "Editar deuda" : "Agregar deuda"} initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
        transition={{ type: "spring", stiffness: 320, damping: 34 }}>
        <header>
          <h2>{editando ? "Editar deuda" : "Agregar deuda"}</h2>
          <button className="btn icono fantasma" onClick={alCerrar} aria-label="Cerrar"><X size={18} /></button>
        </header>
        <form className="cuerpo" onSubmit={enviar}>
          {error && <Aviso tipo="error">{error}</Aviso>}
          {campo("acreedor", "¿A quién le debes? (banco, proveedor, familiar)", "text", { required: true, maxLength: 120 })}
          <div className="campo">
            <label htmlFor="d-tipo">Tipo de deuda</label>
            <select id="d-tipo" className="select" value={f.tipo} onChange={(e) => poner("tipo", e.target.value as TipoDeuda)}>
              {TIPOS.map((t) => <option key={t.v} value={t.v}>{t.t}</option>)}
            </select>
          </div>
          <div className="grid grid-2" style={{ gap: 12 }}>
            {campo("saldo_actual", "Cuánto debes hoy ($)", "number", { required: true, min: 0, step: "0.01" })}
            {campo("monto_original", "Monto original ($)", "number", { min: 0, step: "0.01" })}
            {campo("tasa", "Tasa de interés anual (%)", "number", { min: 0, max: 500, step: "0.01" })}
            {campo("cat", "CAT (%) · opcional", "number", { min: 0, step: "0.01" })}
            {!revolvente && campo("plazo_meses", "Plazo total (meses)", "number", { min: 1, step: "1" })}
            {!revolvente && campo("pago_mensual", "Pago mensual ($) · si lo sabes", "number", { min: 0, step: "0.01" })}
            {revolvente && campo("limite_credito", "Límite de crédito ($)", "number", { min: 0, step: "0.01" })}
            {campo("fecha_inicio", "Fecha en que empezó", "date", { required: true })}
            {revolvente && campo("dia_corte", "Día de corte", "number", { min: 1, max: 31 })}
            {campo("dia_limite_pago", "Día límite de pago", "number", { min: 1, max: 31 })}
            {campo("comisiones_mensuales", "Comisiones al mes ($)", "number", { min: 0, step: "0.01" })}
            {campo("tasa_moratoria", "Tasa moratoria anual (%) · opcional", "number", { min: 0, step: "0.01" })}
          </div>
          <label className="fila" style={{ gap: 8 }}>
            <input type="checkbox" checked={f.aplica_iva_intereses} onChange={(e) => poner("aplica_iva_intereses", e.target.checked)} />
            <span>Cobran IVA (16%) sobre los intereses <span className="muted">· lo normal en tarjetas y créditos de bancos</span></span>
          </label>
          <div className="campo">
            <label htmlFor="d-uso">¿Para qué se usó?</label>
            <select id="d-uso" className="select" value={f.uso} onChange={(e) => poner("uso", e.target.value as "negocio" | "personal")}>
              <option value="negocio">Para el negocio (sus intereses se pueden deducir)</option><option value="personal">Personal</option>
            </select>
          </div>
          <button className="btn primario" disabled={enviando}>{enviando ? "Guardando…" : "Guardar deuda"}</button>
        </form>
      </motion.aside>
    </>
  );
}

function TarjetaDeuda({ d, editable, alAbonar, alEditar, alLiquidar, alBorrar }: {
  d: Deuda; editable: boolean; alAbonar: () => void; alEditar: () => void; alLiquidar: () => void; alBorrar: () => void;
}) {
  const estado = d.nunca_baja ? "rojo" : d.utilizacion !== null && d.utilizacion > 0.3 ? (d.utilizacion > 0.8 ? "rojo" : "amarillo") : d.tasa_interes_anual > 0.7 ? "rojo" : "verde";
  return (
    <motion.article className="card interactiva pila" layout initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
      <div className="fila-entre" style={{ alignItems: "flex-start" }}>
        <div>
          <span className="eyebrow">{d.tipo_texto}</span>
          <h3>{d.acreedor}</h3>
        </div>
        <Semaforo estado={estado} texto={d.nunca_baja ? "Nunca baja" : undefined} />
      </div>
      <div className="fila-entre">
        <strong className="num" style={{ fontSize: "var(--fs-xl)" }}>{dinero(d.saldo_actual, false)}</strong>
        <span className="muted pequeno">{d.tasa_interes_anual > 0 ? `${pct(d.tasa_interes_anual, 0)} anual` : "sin intereses"}</span>
      </div>
      {d.progreso !== null && (
        <div className="pila" style={{ gap: 4 }}>
          <div className="barra" role="progressbar" aria-valuenow={Math.round(d.progreso * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`Pagado de ${d.acreedor}`}>
            <span style={{ width: `${Math.round(d.progreso * 100)}%` }} />
          </div>
          <span className="mini muted">Llevas pagado {pct(d.progreso, 0)} de {dinero(d.monto_original, false)}</span>
        </div>
      )}
      {d.utilizacion !== null && (
        <div className="pila" style={{ gap: 4 }}>
          <div className="barra" role="progressbar" aria-valuenow={Math.round(d.utilizacion * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`Uso del límite de ${d.acreedor}`}>
            <span style={{ width: `${Math.min(100, Math.round(d.utilizacion * 100))}%`, background: d.utilizacion > 0.8 ? "var(--bad)" : d.utilizacion > 0.3 ? "var(--warn)" : "var(--celeste)" }} />
          </div>
          <span className="mini muted">Usas {pct(d.utilizacion, 0)} de tu límite de {dinero(d.limite_credito, false)}</span>
        </div>
      )}
      <div className="pila" style={{ gap: 2 }}>
        <div className="dato"><span className="k">Pago de este mes</span><span className="v num">{dinero(d.proximo_pago.monto, false)}</span></div>
        <div className="dato"><span className="k">Fecha límite</span><span className="v num">{fechaCorta(d.proximo_pago.fecha)}</span></div>
        {d.pago_minimo !== null && <div className="dato"><span className="k">Para no pagar intereses</span><span className="v num">{dinero(d.pago_sin_intereses, false)}</span></div>}
        <div className="dato"><span className="k">Terminas de pagar</span><span className="v num">{d.nunca_baja ? "nunca, con este pago" : d.fecha_liquidacion ? fechaCorta(d.fecha_liquidacion) : "—"}</span></div>
        <div className="dato"><span className="k">Intereses que pagarás</span><span className="v num">{dinero(d.interes_total, false)}</span></div>
      </div>
      {editable && (
        <div className="fila envolver">
          <button className="btn chico primario" onClick={alAbonar}><Banknote size={14} /> Abonar</button>
          <button className="btn chico" onClick={alEditar}><Pencil size={14} /> Editar</button>
          <button className="btn chico" onClick={alLiquidar}><Flag size={14} /> Ya la liquidé</button>
          <button className="btn chico fantasma peligro" onClick={alBorrar} aria-label={`Eliminar ${d.acreedor}`}><Trash2 size={14} /></button>
        </div>
      )}
    </motion.article>
  );
}

export function Deudas() {
  const { empresa, empresas } = useSesion();
  const id = empresa?.id_empresa;
  const editable = empresas.find((e) => e.id_empresa === id)?.rol !== "consulta";
  const [extra, setExtra] = useState<string>("");
  const [extraAplicado, setExtraAplicado] = useState<number | undefined>(undefined);
  const [version, setVersion] = useState(0);
  const [cajon, setCajon] = useState<{ editando: Deuda | null } | null>(null);
  const [abonando, setAbonando] = useState<Deuda | null>(null);
  const [montoAbono, setMontoAbono] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  const listo = Boolean(id);
  const pn = useApi<PanelDeudas>(listo ? `/empresas/${id}/deudas` : null, { extra: extraAplicado, v: version });
  const p = pn.datos;

  useEffect(() => {
    const t = setTimeout(() => setExtraAplicado(extra.trim() === "" ? undefined : Math.max(0, Number(extra) || 0)), 400);
    return () => clearTimeout(t);
  }, [extra]);

  const refrescar = () => setVersion((v) => v + 1);
  const guardar = async (f: Formulario) => {
    const cuerpo = {
      acreedor: f.acreedor.trim(), tipo: f.tipo, monto_original: num(f.monto_original) ?? 0, saldo_actual: num(f.saldo_actual) ?? 0,
      tasa_interes_anual: (num(f.tasa) ?? 0) / 100, cat: num(f.cat) === null ? null : (num(f.cat) as number) / 100, plazo_meses: num(f.plazo_meses),
      pago_mensual: num(f.pago_mensual), limite_credito: num(f.limite_credito), fecha_inicio: f.fecha_inicio, dia_corte: num(f.dia_corte),
      dia_limite_pago: num(f.dia_limite_pago), comisiones_mensuales: num(f.comisiones_mensuales) ?? 0,
      tasa_moratoria_anual: num(f.tasa_moratoria) === null ? null : (num(f.tasa_moratoria) as number) / 100, aplica_iva_intereses: f.aplica_iva_intereses, uso: f.uso,
    };
    if (cajon?.editando) await api.put(`/empresas/${id}/deudas/${cajon.editando.id_deuda}`, cuerpo);
    else await api.post(`/empresas/${id}/deudas`, cuerpo);
    setCajon(null);
    refrescar();
  };
  const accion = async (fn: () => Promise<unknown>) => {
    try {
      setAviso(null);
      await fn();
      refrescar();
    } catch (e) {
      setAviso((e as Error).message);
    }
  };
  const abonar = () => abonando && accion(async () => {
    await api.post(`/empresas/${id}/deudas/${abonando.id_deuda}/pagos`, { fecha: new Date().toISOString().slice(0, 10), monto: Number(montoAbono) });
    setAbonando(null);
    setMontoAbono("");
  });

  const kp = p?.kpis;
  const e = p?.estrategias;
  return (
    <Pagina eyebrow="Deudas" titulo="¿Cuánto debes y cuándo terminas de pagar?"
      descripcion="Todas tus deudas en un solo lugar: cuánto te cuestan, cuándo vencen y cuál conviene pagar primero."
      acciones={editable && <button className="btn primario" onClick={() => setCajon({ editando: null })}><Plus size={16} /> Agregar deuda</button>}>
      {pn.error && <Aviso tipo="error">{pn.error}</Aviso>}
      {aviso && <Aviso tipo="error">{aviso}</Aviso>}
      {!p ? (
        <div className="grid grid-kpi">{[0, 1, 2, 3].map((i) => <TarjetaCargando key={i} alto={50} />)}</div>
      ) : !p.hay_deudas || !kp ? (
        <EstadoVacio icono={CreditCard} titulo="No tienes deudas registradas" texto="Agrega tus tarjetas, créditos o préstamos para saber cuánto te cuestan y cuál conviene pagar primero."
          accion={editable ? <button className="btn primario" onClick={() => setCajon({ editando: null })}><Plus size={16} /> Agregar mi primera deuda</button> : undefined} />
      ) : (
        <>
          <div className="grid grid-kpi">
            <KpiCard indice={0} etiqueta="Lo que debes" tecnico="Deuda total (saldo)" valor={kp.deuda_total} formato={(n) => dinero(Math.round(n), false)} nota={`a un año: ${dineroCompacto(kp.deuda_corto_plazo)} se paga`} />
            <KpiCard indice={1} etiqueta="Pagas al mes" tecnico="Pago mensual total (incluye comisiones)" valor={kp.pago_mensual_total} formato={(n) => dinero(Math.round(n), false)}
              nota={`próx. 7 días: ${dineroCompacto(kp.proximos_pagos["7_dias"])} · 30 días: ${dineroCompacto(kp.proximos_pagos["30_dias"])}`} />
            <KpiCard indice={2} etiqueta="Te cuesta de intereses" tecnico="Costo mensual de la deuda = intereses + IVA + comisiones" valor={kp.costo_mensual} formato={(n) => dinero(Math.round(n), false)} nota="cada mes" />
            <KpiCard indice={3} etiqueta="De tus ventas se va en deudas" tecnico="Pago mensual total / ventas mensuales proyectadas" valor={kp.pct_ventas === null ? null : kp.pct_ventas * 100} formato={(n) => `${n.toFixed(0)}%`}
              nota={kp.semaforo_pct_ventas === "verde" ? "sano (menos de 15%)" : kp.semaforo_pct_ventas === "amarillo" ? "atención (15% a 30%)" : "alto (más de 30%)"} />
            <KpiCard indice={4} etiqueta="¿Te alcanza para pagarlas?" tecnico="Cobertura del servicio de deuda (DSCR) = utilidad mensual / pagos de deuda" valor={kp.dscr} formato={(n) => `${n.toFixed(2)} veces`}
              nota={kp.semaforo_dscr === "verde" ? "sano (1.25 o más)" : kp.semaforo_dscr === "amarillo" ? "justo (1.0 a 1.25)" : "no alcanza (menos de 1)"} />
            <KpiCard indice={5} etiqueta="Libre de deudas" tecnico="Fecha en que terminas con el plan actual" valor={kp.fecha_libre ? new Date(kp.fecha_libre).getFullYear() : null} formato={(n) => String(Math.round(n))}
              nota={kp.fecha_libre ? fechaLarga(kp.fecha_libre) : "con el plan actual no se liquida"} />
          </div>

          {p.alertas.length > 0 && <div className="pila">{p.alertas.map((a, i) => <TarjetaAlerta key={a.id} alerta={a} indice={i} compacta />)}</div>}
          <ClaraResumen ruta={id ? `/empresas/${id}/deudas/clara` : null} version={version} />

          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))" }}>
            {p.deudas.map((d) => (
              <TarjetaDeuda key={d.id_deuda} d={d} editable={editable} alAbonar={() => setAbonando(d)} alEditar={() => setCajon({ editando: d })}
                alLiquidar={() => window.confirm(`¿Marcar "${d.acreedor}" como liquidada?`) && accion(() => api.post(`/empresas/${id}/deudas/${d.id_deuda}/liquidar`))}
                alBorrar={() => window.confirm(`¿Eliminar "${d.acreedor}" y sus abonos? Esto no se puede deshacer.`) && accion(() => api.delete(`/empresas/${id}/deudas/${d.id_deuda}`))} />
            ))}
          </div>

          <div className="grid grid-2">
            <Tarjeta retraso={0.04}>
              <TituloTarjeta icono={TrendingDown} titulo="Tu deuda bajando" sub="Cuánto debes mes con mes hasta llegar a cero" />
              <Leyenda items={[{ nombre: "Plan actual", color: SERIE.ventas, tipo: "linea" }, { nombre: "Avalancha", color: SERIE.utilidad, tipo: "linea" }, { nombre: "Bola de nieve", color: SERIE.gastos, tipo: "punteada" }]} />
              <div style={{ height: 260 }}>
                <ResponsiveContainer>
                  <LineChart data={p.saldo_series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--grid)" />
                    <XAxis dataKey="fecha" {...EJE} tickFormatter={fechaCorta} minTickGap={40} />
                    <YAxis {...EJE} width={60} tickFormatter={dineroCompacto} />
                    <Tooltip content={<TooltipGrafica titulo={(l) => fechaCorta(String(l))} nombres={{ actual: "Plan actual", avalancha: "Avalancha", bola_de_nieve: "Bola de nieve" }} />} />
                    <Line dataKey="actual" stroke={SERIE.ventas} strokeWidth={2} dot={false} animationDuration={900} />
                    <Line dataKey="avalancha" stroke={SERIE.utilidad} strokeWidth={2} dot={false} animationDuration={900} />
                    <Line dataKey="bola_de_nieve" stroke={SERIE.gastos} strokeWidth={2} strokeDasharray="5 4" dot={false} animationDuration={900} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Tarjeta>
            <Tarjeta retraso={0.08}>
              <TituloTarjeta icono={Scale} titulo="¿A dónde se va tu pago?" sub="Próximos 12 meses: lo que baja tu deuda vs. lo que se va en intereses" />
              <Leyenda items={[{ nombre: "Abono a la deuda", color: SERIE.ventas }, { nombre: "Intereses, IVA y comisiones", color: SERIE.gastos }]} />
              <div style={{ height: 260 }}>
                <ResponsiveContainer>
                  <BarChart data={p.barras_pago} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--grid)" />
                    <XAxis dataKey="etiqueta" {...EJE} tickFormatter={(v) => fechaCorta(String(v)).split(" ")[1]} />
                    <YAxis {...EJE} width={56} tickFormatter={dineroCompacto} />
                    <Tooltip content={<TooltipGrafica titulo={(l) => fechaCorta(String(l))} nombres={{ capital: "Abono a la deuda", interes: "Intereses, IVA y comisiones" }} />} cursor={{ fill: "var(--surface-hover)" }} />
                    <Bar dataKey="capital" stackId="p" fill={SERIE.ventas} maxBarSize={26} activeBar={{ stroke: "none", fillOpacity: 0.85 }} />
                    <Bar dataKey="interes" stackId="p" fill={SERIE.gastos} radius={[4, 4, 0, 0]} maxBarSize={26} activeBar={{ stroke: "none", fillOpacity: 0.85 }} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Tarjeta>
          </div>

          {e && (
            <Tarjeta retraso={0.12}>
              <TituloTarjeta icono={Flag} titulo="¿Cuál deuda pago primero?" sub="Comparamos dos formas de usar el mismo dinero cada mes" />
              <div className="fila envolver">
                <div className="campo" style={{ maxWidth: 260 }}>
                  <label htmlFor="extra">Dinero extra al mes para tus deudas ($)</label>
                  <input id="extra" className="input" type="number" min={0} step={100} placeholder={String(e.extra_mensual)} value={extra} onChange={(ev) => setExtra(ev.target.value)} />
                </div>
                <span className="mini muted justificado" style={{ maxWidth: 380 }}>Si lo dejas vacío usamos {dinero(e.extra_mensual, false)}, una parte de lo que te sobra después de pagar tus deudas. Lo que se libera al terminar una deuda se suma al extra.</span>
              </div>
              <div className="tabla-envoltura">
                <table className="tabla">
                  <thead><tr><th>Plan</th><th className="der">Intereses totales</th><th className="der">Terminas</th><th>Orden en que se liquidan</th></tr></thead>
                  <tbody>
                    {([["actual", "Como vas hoy (sin extra)", e.actual], ["avalancha", "Avalancha · primero la tasa más alta", e.avalancha], ["bola_de_nieve", "Bola de nieve · primero la deuda más chica", e.bola_de_nieve]] as const).map(([k, t, plan]) => (
                      <tr key={k} style={e.recomendada === k ? { background: "var(--ok-soft)" } : undefined}>
                        <td><strong>{t}</strong>{e.recomendada === k && <span className="chip ok" style={{ marginLeft: 8 }}>Recomendado</span>}</td>
                        <td className="der num">{dinero(plan.interes_total, false)}</td>
                        <td className="der num">{plan.fecha_liquidacion ? fechaLarga(plan.fecha_liquidacion) : "nunca"}{plan.meses ? <span className="muted mini"> ({numero(plan.meses)} meses)</span> : null}</td>
                        <td className="pequeno muted">{plan.orden.join(" → ") || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mini muted justificado">
                {e.recomendada === "avalancha"
                  ? `Recomendamos avalancha: con ${dinero(e.extra_mensual, false)} extra al mes te ahorra ${dinero(e.ahorro_avalancha_vs_bola, false)} más que bola de nieve.`
                  : `La diferencia entre ambos planes es menor a $500 (${dinero(e.ahorro_avalancha_vs_bola, false)}), así que puedes elegir bola de nieve: liquidas deudas pequeñas más rápido y eso motiva.`}{" "}
                Orientación general, no constituye asesoría financiera.
              </p>
            </Tarjeta>
          )}

          <div className="grid grid-2">
            <Tarjeta retraso={0.16}>
              <TituloTarjeta icono={CalendarClock} titulo="Pagos de los próximos 60 días" />
              {(p.calendario ?? []).length === 0 ? <p className="muted">No tienes pagos en los próximos 60 días.</p> : (
                <ul className="pila" style={{ listStyle: "none", margin: 0, padding: 0, gap: 8 }}>
                  {(p.calendario ?? []).map((c, i) => (
                    <li key={`${c.fecha}${c.acreedor}${i}`} className="dato"><span className="k">{fechaLarga(c.fecha)} · {c.acreedor}</span><span className="v num">{dinero(c.monto, false)}</span></li>
                  ))}
                </ul>
              )}
            </Tarjeta>
            <Tarjeta retraso={0.2}>
              <TituloTarjeta icono={Scale} titulo="¿Puedo pedir otro crédito?" sub="Una referencia, no una oferta" />
              <div className="pila">
                <div className="dato"><span className="k">Pago mensual máximo recomendado</span><span className="v num">{dinero(kp.capacidad_endeudamiento.pago_maximo, false)}</span></div>
                <div className="dato"><span className="k">Crédito equivalente a {kp.capacidad_endeudamiento.plazo_meses} meses</span><span className="v num">{dinero(kp.capacidad_endeudamiento.monto_equivalente, false)}</span></div>
                <div className="dato"><span className="k">Tasa promedio de tus deudas</span><span className="v num">{kp.tasa_promedio_ponderada === null ? "—" : pct(kp.tasa_promedio_ponderada, 1)}</span></div>
                <div className="dato"><span className="k">Deuda / utilidad de un año</span><span className="v num">{kp.razon_deuda_utilidad_anual === null ? "—" : `${kp.razon_deuda_utilidad_anual.toFixed(2)} veces`}</span></div>
                {kp.utilizacion_tarjetas !== null && <div className="dato"><span className="k">Uso de tus tarjetas</span><span className="v num">{pct(kp.utilizacion_tarjetas, 0)}</span></div>}
              </div>
              <p className="mini muted justificado">Se calcula con tu utilidad mensual proyectada (que alcance 1.25 veces tus pagos). Considera un financiamiento solo como opción a evaluar; compara costos y plazos antes de decidir. Orientación general, no constituye asesoría financiera.</p>
            </Tarjeta>
          </div>
        </>
      )}

      <AnimatePresence>
        {cajon && <Cajon key={cajon.editando?.id_deuda ?? "nueva"} editando={cajon.editando} alCerrar={() => setCajon(null)} alGuardar={guardar} />}
      </AnimatePresence>

      <AnimatePresence>
        {abonando && (
          <>
            <motion.div className="velo" style={{ zIndex: 65 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setAbonando(null)} />
            <motion.div className="card pila" role="dialog" aria-label={`Abonar a ${abonando.acreedor}`}
              style={{ position: "fixed", zIndex: 70, left: "50%", top: "30%", translate: "-50% 0", width: "min(420px, 92vw)" }}
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
              <h3>Abonar a {abonando.acreedor}</h3>
              <div className="campo">
                <label htmlFor="abono">¿Cuánto pagaste? ($)</label>
                <input id="abono" className="input" type="number" min={1} step="0.01" autoFocus value={montoAbono} onChange={(ev) => setMontoAbono(ev.target.value)} />
              </div>
              <p className="mini muted justificado">Primero se cubren los intereses y el IVA del mes y el resto baja lo que debes.</p>
              <div className="fila">
                <button className="btn primario" disabled={!(Number(montoAbono) > 0)} onClick={abonar}>Registrar abono</button>
                <button className="btn" onClick={() => setAbonando(null)}>Cancelar</button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </Pagina>
  );
}
