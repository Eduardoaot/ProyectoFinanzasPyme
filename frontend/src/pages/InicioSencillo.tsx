import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle, ArrowRight, BarChart3, CheckCircle2, ChevronRight, CreditCard, FileSpreadsheet, Landmark,
  MousePointerClick, OctagonAlert, Package, ShoppingBasket, Sparkles, TrendingUp, type LucideIcon,
} from "lucide-react";
import { lazy, Suspense, useState, type ReactNode } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Link } from "react-router-dom";
import { indicePicado, TooltipGrafica } from "../components/charts/comun";
import type { TemaClara } from "../components/sencillo/VentanaClara";
import { Aviso, Cambio, Esqueleto } from "../components/ui/basicos";
import { Emergente, IrASeccion, ListaCifras } from "../components/ui/Emergente";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { diaMes, dinero, dineroCompacto, fechaCorta, fechaLarga, numero, rangoDias } from "../lib/formato";
import type { Estado3, Inicio, ProductoSencillo, Semaforo } from "../lib/tipos";

// La ventana (con su lector de Markdown) se descarga la primera vez que alguien toca "Preguntar".
const VentanaClara = lazy(() => import("../components/sencillo/VentanaClara").then((m) => ({ default: m.VentanaClara })));

const entero = (n: number) => dinero(Math.round(n), false);

function cantidad(n: number, unidad: string) {
  const plural = n === 1 || ["kg", "g", "l", "ml"].includes(unidad) || unidad.endsWith("s") ? unidad : `${unidad}s`;
  return `${numero(n)} ${plural}`;
}

const ESTADO: Record<Estado3, { texto: string; Icono: LucideIcon }> = {
  verde: { texto: "Vas bien", Icono: CheckCircle2 },
  amarillo: { texto: "Pon atención", Icono: AlertTriangle },
  rojo: { texto: "Cuidado", Icono: OctagonAlert },
};

const INVENTARIO: Record<Semaforo, string> = {
  verde: "Tienes suficiente",
  amarillo: "Pide pronto",
  rojo: "Se te acaba",
  sin_movimiento: "No se está vendiendo",
};

// Lo que Clara explica en cada tarjeta: escrito por personas, en palabras de todos los días.
const TEMAS: Record<string, TemaClara> = {
  general: {
    titulo: "Pregúntale a Clara",
    explicacion: [
      "Clara es una ayudante que conoce los números de tu negocio. Puedes preguntarle lo que quieras, como si le preguntaras a alguien de confianza.",
      "Si no sabes qué preguntar, toca una de estas preguntas.",
    ],
    preguntas: [
      { texto: "¿Estoy ganando dinero?", envia: "¿Estoy ganando?" },
      { texto: "¿Qué producto me deja más?" },
      { texto: "¿En qué gasto demasiado?", envia: "¿Dónde gasto demasiado?" },
      { texto: "¿Me va a alcanzar el dinero?" },
    ],
  },
  como_te_fue: {
    titulo: "¿Cómo te fue?",
    explicacion: [
      "«Vendiste» es todo el dinero que te pagaron tus clientes.",
      "«Gastaste» es lo que te costó la mercancía que vendiste más lo que pagaste para tener abierto el negocio: renta, luz, sueldos, bolsas…",
      "«Te quedó» es lo que sobra: lo que vendiste menos lo que gastaste. Esa es tu ganancia de verdad.",
    ],
    preguntas: [
      { texto: "¿Cuánto gané este mes?" },
      { texto: "¿Qué quiere decir «te quedó»?", envia: "¿Qué significa utilidad?" },
      { texto: "¿Por qué vendí menos que el mes pasado?" },
      { texto: "¿En qué gasto demasiado?", envia: "¿Dónde gasto demasiado?" },
    ],
  },
  ventas: {
    titulo: "Tus ventas mes por mes",
    explicacion: [
      "Cada barra es un mes. Entre más alta la barra, más vendiste ese mes.",
      "La barra más oscura es el mes más reciente. Compárala con las demás para ver si vas subiendo o bajando.",
    ],
    preguntas: [
      { texto: "¿Cuánto vendí este mes?" },
      { texto: "¿En qué mes vendí más?" },
      { texto: "¿Vendí más o menos que el mes pasado?", envia: "Compara mis ventas con el mes pasado" },
      { texto: "¿Qué hago para vender más?" },
    ],
  },
  productos: {
    titulo: "Tus productos",
    explicacion: [
      "Aquí están los productos que más dinero te dejan, del que más al que menos.",
      "«Te dejó» es lo que ganaste con ese producto: lo que te pagaron menos lo que a ti te costó.",
      "La última columna te dice si todavía tienes suficiente o si ya se te está acabando y tienes que pedir más.",
    ],
    preguntas: [
      { texto: "¿Qué producto me deja más?" },
      { texto: "¿Qué productos tengo que volver a pedir?", envia: "¿Qué productos tengo que resurtir?" },
      { texto: "¿Qué productos me dejan poco?" },
    ],
  },
  lo_que_viene: {
    titulo: "Lo que viene",
    explicacion: [
      "Con lo que has vendido en los últimos meses, el sistema calcula cuánto vas a vender, más o menos, en las próximas semanas. Es un cálculo aproximado, no una promesa.",
      "También revisa si el dinero que tienes te alcanza para tus pagos, y qué mercancía te conviene comprar pronto para que no te falte.",
    ],
    preguntas: [
      { texto: "¿Cuánto voy a vender el próximo mes?" },
      { texto: "¿Me va a alcanzar el dinero?" },
      { texto: "¿Qué tengo que comprar?", envia: "¿Qué productos tengo que resurtir?" },
      { texto: "¿Cómo saben cuánto voy a vender?", envia: "¿Qué es el pronóstico?" },
    ],
  },
  impuestos: {
    titulo: "Tus impuestos",
    explicacion: [
      "El SAT es la oficina del gobierno que cobra los impuestos. Cada mes te toca pagarle una parte de lo que vendes o de lo que ganas.",
      "Lo más fácil es ir apartando ese dinero conforme vendes, para que el día de pagar no te tome por sorpresa.",
      "Además, cada año en abril presentas la declaración anual, donde se ajusta lo que pagaste mes con mes.",
    ],
    preguntas: [
      { texto: "¿Por qué le tengo que pagar al SAT?", envia: "¿Qué es el SAT?" },
      { texto: "¿Cuánto tengo que apartar?", envia: "¿Cuánto debo apartar para el SAT?" },
      { texto: "¿Qué es el IVA?" },
      { texto: "¿Qué es el ISR?" },
    ],
  },
  deudas: {
    titulo: "Tus deudas",
    explicacion: [
      "Aquí está lo que debes: tarjetas, préstamos o lo que le debes a tus proveedores.",
      "Los intereses son lo que te cobran de más por prestarte. Por eso conviene pagar primero la deuda que más intereses te cobra.",
    ],
    preguntas: [
      { texto: "¿Cuánto debo en total?" },
      { texto: "¿Cuál deuda pago primero?" },
      { texto: "¿Qué son los intereses?" },
    ],
  },
};

/** El mini resumen de un producto le pasa a Clara su consejo y las preguntas de "Tus productos". */
function temaProducto(p: ProductoSencillo): TemaClara {
  return {
    titulo: p.nombre,
    explicacion: [p.consejo, "«Te deja» es lo que ganas con cada pieza: lo que te pagan menos lo que a ti te costó."],
    preguntas: TEMAS.productos.preguntas,
  };
}

const ICONO_ESTADO: Record<Estado3, LucideIcon> = { verde: CheckCircle2, amarillo: AlertTriangle, rojo: OctagonAlert };

/**
 * Tarjeta del tablero. Si tiene `onAbrir`, picar su contenido abre el detalle en una ventana;
 * al pie quedan los dos botones chicos: preguntarle a Clara e ir a la sección.
 */
function Panel({ icono: Icono, titulo, tema, detalles, clase = "", indice = 0, children, onPreguntar, onAbrir }: {
  icono: LucideIcon; titulo: string; tema: string; detalles: string; clase?: string; indice?: number;
  children: ReactNode; onPreguntar: (tema: string) => void; onAbrir?: () => void;
}) {
  return (
    <motion.section className={`panel-sencillo ${clase}`} aria-label={titulo}
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: indice * 0.05 }}>
      <h2 className="panel-titulo"><span className="icono-sencillo" aria-hidden="true"><Icono size={18} /></span>{titulo}</h2>
      {onAbrir ? (
        <div className="panel-cuerpo picable" role="button" tabIndex={0} aria-haspopup="dialog" aria-label={`Ver detalle: ${titulo}`}
          onClick={onAbrir} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onAbrir(); } }}>
          {children}
          <span className="pista-panel" aria-hidden="true">Ver detalle <ChevronRight size={14} /></span>
        </div>
      ) : children}
      <div className="panel-acciones">
        <button type="button" className="accion-mini clara" onClick={() => onPreguntar(tema)}
          aria-label={`Pregúntale a Clara: ${titulo}`} title="Pregúntale a Clara qué significa">
          <Sparkles size={15} aria-hidden="true" /> Preguntar
        </button>
        <Link to={detalles} className="accion-mini" aria-label={`Ir a la sección: ${titulo}`} title="Abrir la sección completa">
          Ir a la sección <ArrowRight size={15} aria-hidden="true" />
        </Link>
      </div>
    </motion.section>
  );
}

/** Una cifra con su nombre arriba, como en las tarjetas de un tablero. */
function Cifra({ nombre, valor, tono }: { nombre: string; valor: string; tono?: "bien" | "mal" }) {
  return (
    <div className={`cifra-sencilla ${tono ?? ""}`}>
      <span>{nombre}</span>
      <strong>{valor}</strong>
    </div>
  );
}

/** Pie de los detalles del modo sencillo: Clara (ventana de preguntas) y la sección completa. */
function PieDetalle({ onClara, a }: { onClara: () => void; a: string }) {
  return (
    <>
      <button type="button" className="btn celeste" onClick={onClara}><Sparkles size={16} aria-hidden="true" /> Pregúntale a Clara</button>
      <IrASeccion a={a} texto="Ir a la sección" />
    </>
  );
}

function GraficaVentas({ meses, onMes }: { meses: Inicio["ventas_por_mes"]; onMes: (i: number) => void }) {
  return (
    <>
      <div className="grafica-sencilla" role="img"
        aria-label={`Ventas por mes: ${meses.map((m) => `${m.etiqueta} ${entero(m.ventas)}`).join(", ")}`}>
        <ResponsiveContainer>
          <BarChart data={meses} margin={{ top: 22, right: 4, bottom: 0, left: 4 }} style={{ cursor: "pointer" }}
            onClick={(e) => { const i = indicePicado(e); if (i !== null) onMes(i); }}>
            <XAxis dataKey="etiqueta" axisLine={false} tickLine={false} tick={{ fill: "var(--ink-2)", fontSize: 13, fontWeight: 600 }} />
            <Tooltip content={<TooltipGrafica nombres={{ ventas: "Vendiste" }} />} cursor={{ fill: "var(--surface-hover)" }} />
            <Bar dataKey="ventas" radius={[4, 4, 0, 0]} maxBarSize={48} animationDuration={700}>
              {meses.map((m) => (
                <Cell key={m.etiqueta} fill={m.actual ? "var(--s1)" : "color-mix(in srgb, var(--s1) 40%, var(--surface))"} />
              ))}
              <LabelList dataKey="ventas" position="top" formatter={(v) => dineroCompacto(Number(v))}
                style={{ fill: "var(--ink-2)", fontSize: 12, fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="pista-grafica"><MousePointerClick size={13} aria-hidden="true" /> Toca una barra para ver ese mes.</p>
    </>
  );
}

/** Lo que se abre al picar algo del tablero. */
type Detalle =
  | { tipo: "como_te_fue" | "lo_que_viene" | "compras" | "impuestos" | "deudas" }
  | { tipo: "mes"; i: number }
  | { tipo: "producto"; p: ProductoSencillo };

function DetalleSencillo({ d, x, onCerrar, onClara }: {
  d: Inicio; x: Detalle; onCerrar: () => void; onClara: (tema: TemaClara) => void;
}) {
  const clara = (tema: TemaClara) => () => { onCerrar(); onClara(tema); };
  const c = d.como_te_fue;
  const v = d.lo_que_viene;

  if (x.tipo === "como_te_fue" && c) {
    const { Icono, texto } = ESTADO[c.estado];
    return (
      <Emergente ancho="chico" icono={TrendingUp} titulo={`¿Cómo te fue en ${c.mes}?`} onCerrar={onCerrar}
        pie={<PieDetalle onClara={clara(TEMAS.como_te_fue)} a="/resumen" />}>
        <p className={`estado-sencillo ${c.estado}`}><Icono size={18} aria-hidden="true" /> {texto}</p>
        <p>{c.frase}</p>
        <ListaCifras filas={[
          { nombre: "Vendiste", valor: entero(c.ventas) },
          { nombre: "Gastaste (mercancía y gastos)", valor: `− ${entero(c.gastaste)}` },
          { nombre: c.te_quedo < 0 ? "Perdiste" : "Te quedó", valor: entero(Math.abs(c.te_quedo)), tono: c.te_quedo < 0 ? "mal" : "bien" },
          ...(c.cambio_ventas !== null ? [{ nombre: "Contra el mes anterior", valor: <Cambio valor={c.cambio_ventas} /> }] : []),
        ]} />
      </Emergente>
    );
  }

  if (x.tipo === "mes") {
    const m = d.ventas_por_mes[x.i];
    const ant = d.ventas_por_mes[x.i - 1];
    const mejor = Math.max(...d.ventas_por_mes.map((s) => s.ventas));
    if (!m) return null;
    return (
      <Emergente ancho="chico" icono={BarChart3} titulo={`Lo que vendiste en ${m.etiqueta}`} onCerrar={onCerrar}
        pie={<PieDetalle onClara={clara(TEMAS.ventas)} a="/finanzas" />}>
        <div className="emergente-cifra">
          <strong>{entero(m.ventas)}</strong>
          {ant && <Cambio valor={ant.ventas ? (m.ventas - ant.ventas) / ant.ventas : null} />}
        </div>
        {ant && <p className="muted">En {ant.etiqueta} habías vendido {entero(ant.ventas)}.</p>}
        {m.ventas === mejor && d.ventas_por_mes.length > 1 && (
          <p className="nota-sencilla bien"><CheckCircle2 size={18} aria-hidden="true" /><span>Es tu mejor mes de los últimos {d.ventas_por_mes.length}.</span></p>
        )}
      </Emergente>
    );
  }

  if (x.tipo === "lo_que_viene" && v) {
    return (
      <Emergente ancho="chico" icono={TrendingUp} titulo={`Lo que viene en ${v.mes}`} subtitulo="Cálculo aproximado con tus ventas recientes"
        onCerrar={onCerrar} pie={<PieDetalle onClara={clara(TEMAS.lo_que_viene)} a="/proyecciones" />}>
        <ListaCifras filas={[
          { nombre: "Vas a vender cerca de", valor: entero(v.ventas_esperadas) },
          { nombre: "Te quedarían unos", valor: entero(v.ganancia_esperada), tono: v.ganancia_esperada < 0 ? "mal" : "bien" },
          { nombre: "Dinero que tienes hoy", valor: entero(v.efectivo_hoy) },
          { nombre: "A fin de mes tendrías", valor: entero(v.efectivo_fin_de_mes), tono: "fuerte" },
        ]} />
        <p className={`nota-sencilla ${v.te_alcanza ? "bien" : "mal"}`}>
          {v.te_alcanza ? <CheckCircle2 size={18} aria-hidden="true" /> : <OctagonAlert size={18} aria-hidden="true" />}
          <span>{v.te_alcanza ? "Sí te alcanza el dinero para tus pagos." : `El ${fechaLarga(v.fecha_riesgo ?? "")} podrías quedarte con muy poco dinero.`}</span>
        </p>
      </Emergente>
    );
  }

  if (x.tipo === "compras" && v) {
    return (
      <Emergente ancho="chico" icono={ShoppingBasket} titulo="Compra pronto" subtitulo="Para que no te falte mercancía" onCerrar={onCerrar}
        pie={<PieDetalle onClara={clara(TEMAS.lo_que_viene)} a="/proyecciones" />}>
        {v.comprar.length > 0 ? (
          <ListaCifras filas={[
            ...v.comprar.map((p) => ({ nombre: <>{p.nombre} <span className="muted">· {cantidad(p.cantidad, p.unidad)}</span></>, valor: entero(p.costo) })),
            { nombre: "En total, unos", valor: entero(v.total_compra), tono: "fuerte" as const },
          ]} />
        ) : (
          <p className="nota-sencilla bien"><CheckCircle2 size={18} aria-hidden="true" /><span>Por ahora no necesitas comprar mercancía.</span></p>
        )}
      </Emergente>
    );
  }

  if (x.tipo === "impuestos" && d.impuestos) {
    const t = d.impuestos;
    const h = t.hasta_la_anual;
    return (
      <Emergente ancho="chico" icono={Landmark} titulo="Tus impuestos" subtitulo={t.regimen} onCerrar={onCerrar}
        pie={<PieDetalle onClara={clara(TEMAS.impuestos)} a="/impuestos" />}>
        <h3 className="pequeno">Este mes</h3>
        {t.a_pagar > 0 ? (
          <p>
            Por lo que vendiste <strong>{rangoDias(t.periodo_desde, t.periodo_hasta)}</strong> debes <strong>{entero(t.a_pagar)}</strong> de impuestos.
          </p>
        ) : (
          <p>Por lo que vendiste <strong>{rangoDias(t.periodo_desde, t.periodo_hasta)}</strong> no te toca pagar impuestos.</p>
        )}
        {t.saldo_a_favor > 0 && <ListaCifras filas={[{ nombre: "Saldo a tu favor (IVA)", valor: entero(t.saldo_a_favor), tono: "bien" }]} />}

        <h3 className="pequeno">De aquí a la declaración anual ({fechaLarga(h.fecha_anual)})</h3>
        <ListaCifras filas={[
          { nombre: `${h.pagos_mensuales} pagos mensuales (uno cada mes)`, valor: entero(h.total_mensuales) },
          { nombre: "Ajuste en la declaración anual", valor: h.ajuste_anual === null ? "No se puede estimar" : entero(h.ajuste_anual) },
          { nombre: "En total, más o menos", valor: entero(h.total), tono: "fuerte" },
        ]} />
        <p className="emergente-explica">
          Cada mes pagas lo del mes anterior, a más tardar el día 17. En abril presentas la declaración anual, donde se ajusta lo de
          todo el año. Los pagos que vienen se calcularon con el promedio de tus últimos meses: es un aproximado.
        </p>
      </Emergente>
    );
  }

  if (x.tipo === "deudas" && d.deudas) {
    const t = d.deudas;
    return (
      <Emergente ancho="chico" icono={CreditCard} titulo="Tus deudas" onCerrar={onCerrar}
        pie={<PieDetalle onClara={clara(TEMAS.deudas)} a="/deudas" />}>
        <ListaCifras filas={[
          { nombre: "Debes en total", valor: entero(t.total), tono: "fuerte" },
          { nombre: "Pagas al mes unos", valor: entero(t.pago_del_mes) },
          ...(t.proximo_pago ? [{ nombre: `Próximo pago (${t.proximo_pago.acreedor})`, valor: `${entero(t.proximo_pago.monto)} · ${fechaCorta(t.proximo_pago.fecha)}` }] : []),
        ]} />
        {t.paga_primero && <p className="emergente-explica">Si te sobra dinero, abona primero a <strong>{t.paga_primero}</strong>: es la que más te conviene liquidar.</p>}
      </Emergente>
    );
  }

  if (x.tipo === "producto") {
    const p = x.p;
    const deja = p.precio - p.costo;
    const Icono = ICONO_ESTADO[p.consejo_estado];
    return (
      <Emergente ancho="chico" icono={Package} titulo={p.nombre}
        subtitulo={<span className={`semaforo ${p.inventario}`}>{INVENTARIO[p.inventario]}</span>} onCerrar={onCerrar}
        pie={<PieDetalle onClara={clara(temaProducto(p))} a="/productos" />}>
        <div className="mini-producto">
          <Cifra nombre="Lo vendes en" valor={dinero(p.precio)} />
          <Cifra nombre="Te cuesta" valor={dinero(p.costo)} />
          <Cifra nombre={`Te deja por ${p.unidad}`} valor={dinero(deja)} tono={deja < 0 ? "mal" : "bien"} />
          <Cifra nombre="Te quedan" valor={cantidad(p.te_quedan, p.unidad)} />
        </div>
        <p className={`nota-sencilla ${p.consejo_estado}`}><Icono size={18} aria-hidden="true" /><span>{p.consejo}</span></p>
      </Emergente>
    );
  }
  return null;
}

export function InicioSencillo() {
  const { usuario, empresa, empresas } = useSesion();
  const id = empresa?.id_empresa;
  const inicio = useApi<Inicio>(id ? `/empresas/${id}/inicio` : null);
  const [tema, setTema] = useState<TemaClara | null>(null);
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const d = inicio.datos;
  const esDueno = empresas.find((e) => e.id_empresa === id)?.rol === "dueno";
  const nombre = usuario?.nombre.split(" ")[0] ?? "";
  const preguntar = (clave: string) => setTema(TEMAS[clave]);

  if (empresa && !empresa.tiene_datos) {
    return (
      <div className="inicio-sencillo">
        <h1>Hola, {nombre}</h1>
        <section className="tarjeta-sencilla">
          <h2><span className="icono-sencillo" aria-hidden="true"><FileSpreadsheet size={22} /></span>Todavía no hay números</h2>
          {esDueno ? (
            <>
              <p className="frase-sencilla">Sube el Excel donde anotas tus ventas y aquí verás cómo te va, de forma muy sencilla.</p>
              <Link to="/importar" className="btn grande primario" style={{ alignSelf: "flex-start" }}>Subir mi Excel <ArrowRight size={20} /></Link>
            </>
          ) : (
            <p className="frase-sencilla">El dueño de este negocio todavía no ha subido sus ventas.</p>
          )}
        </section>
      </div>
    );
  }

  const c = d?.como_te_fue;
  const v = d?.lo_que_viene;
  const COMPRAS_VISIBLES = 3;
  return (
    <div className="inicio-sencillo">
      <div className="saludo-sencillo">
        <h1>Hola, {nombre}</h1>
        <p className="muted pista-saludo"><MousePointerClick size={15} aria-hidden="true" /> Toca cualquier tarjeta para ver su detalle.</p>
      </div>
      {inicio.error && <Aviso tipo="error">{inicio.error}</Aviso>}

      {!d ? (
        <div className="tablero-sencillo" aria-busy="true" aria-label="Cargando">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="panel-sencillo"><Esqueleto alto={22} ancho="50%" /><Esqueleto alto={110} /></div>
          ))}
        </div>
      ) : (
        <>
          {/* Fila de arriba: cómo te fue y la tendencia de ventas, lado a lado. */}
          {(c || d.ventas_por_mes.length > 0) && (
            <div className="tablero-sencillo fila-principal">
              {c && (
                <Panel icono={TrendingUp} titulo={`¿Cómo te fue en ${c.mes}?`} tema="como_te_fue" detalles="/resumen" onPreguntar={preguntar}
                  onAbrir={() => setDetalle({ tipo: "como_te_fue" })}>
                  <p className={`estado-sencillo ${c.estado}`}>
                    {(() => { const { Icono, texto } = ESTADO[c.estado]; return <><Icono size={18} aria-hidden="true" /> {texto}</>; })()}
                  </p>
                  <div className="cuenta-sencilla" aria-label={`Vendiste ${entero(c.ventas)}, gastaste ${entero(c.gastaste)}, te quedó ${entero(c.te_quedo)}`}>
                    <Cifra nombre="Vendiste" valor={entero(c.ventas)} />
                    <span className="signo" aria-hidden="true">−</span>
                    <Cifra nombre="Gastaste" valor={entero(c.gastaste)} />
                    <span className="signo" aria-hidden="true">=</span>
                    <Cifra nombre={c.te_quedo < 0 ? "Perdiste" : "Te quedó"} valor={entero(Math.abs(c.te_quedo))} tono={c.te_quedo < 0 ? "mal" : "bien"} />
                  </div>
                </Panel>
              )}
              {d.ventas_por_mes.length > 0 && (
                <Panel icono={BarChart3} titulo="¿Vendes más o menos que antes?" tema="ventas" detalles="/finanzas" indice={1} onPreguntar={preguntar}>
                  <GraficaVentas meses={d.ventas_por_mes} onMes={(i) => setDetalle({ tipo: "mes", i })} />
                </Panel>
              )}
            </div>
          )}

          {/* Fila del medio: una cifra por tarjeta; el resto se ve al picarla. */}
          {(v || d.impuestos || d.deudas) && (
            <div className="tablero-sencillo fila-secundaria">
              {v && (
                <Panel icono={TrendingUp} titulo={`Lo que viene en ${v.mes}`} tema="lo_que_viene" detalles="/proyecciones" indice={2}
                  onPreguntar={preguntar} onAbrir={() => setDetalle({ tipo: "lo_que_viene" })}>
                  <Cifra nombre="Vas a vender cerca de" valor={entero(v.ventas_esperadas)} />
                  <span className={`chip ${v.te_alcanza ? "ok" : "bad"}`}>
                    {v.te_alcanza ? <CheckCircle2 size={14} aria-hidden="true" /> : <OctagonAlert size={14} aria-hidden="true" />}
                    {v.te_alcanza ? "Te alcanza el dinero" : "Te podría faltar dinero"}
                  </span>
                </Panel>
              )}

              {v && (
                <Panel icono={ShoppingBasket} titulo="Compra pronto" tema="lo_que_viene" detalles="/proyecciones" indice={3}
                  onPreguntar={preguntar} onAbrir={() => setDetalle({ tipo: "compras" })}>
                  {v.comprar.length > 0 ? (
                    <>
                      <Cifra nombre={`${v.comprar.length} ${v.comprar.length === 1 ? "producto" : "productos"}, unos`} valor={entero(v.total_compra)} />
                      <p className="compras-nombres">
                        {v.comprar.slice(0, COMPRAS_VISIBLES).map((p) => p.nombre).join(", ")}
                        {v.comprar.length > COMPRAS_VISIBLES && ` y ${v.comprar.length - COMPRAS_VISIBLES} más`}
                      </p>
                    </>
                  ) : (
                    <span className="chip ok"><CheckCircle2 size={14} aria-hidden="true" /> No necesitas comprar</span>
                  )}
                </Panel>
              )}

              {d.impuestos && (
                <Panel icono={Landmark} titulo="Impuestos" tema="impuestos" detalles="/impuestos" indice={4}
                  onPreguntar={preguntar} onAbrir={() => setDetalle({ tipo: "impuestos" })}>
                  {d.impuestos.a_pagar > 0 ? (
                    <>
                      <Cifra nombre={`Debes por lo vendido ${rangoDias(d.impuestos.periodo_desde, d.impuestos.periodo_hasta)}`}
                        valor={entero(d.impuestos.a_pagar)} />
                    </>
                  ) : (
                    <span className="chip ok"><CheckCircle2 size={14} aria-hidden="true" /> Por {d.impuestos.mes.toLowerCase()} no pagas</span>
                  )}
                  <p className="linea-anual">
                    Hasta la anual ({diaMes(d.impuestos.hasta_la_anual.fecha_anual)}): unos <strong>{entero(d.impuestos.hasta_la_anual.total)}</strong>
                  </p>
                </Panel>
              )}

              {d.deudas && (
                <Panel icono={CreditCard} titulo="Deudas" tema="deudas" detalles="/deudas" indice={5}
                  onPreguntar={preguntar} onAbrir={() => setDetalle({ tipo: "deudas" })}>
                  <Cifra nombre="Debes en total" valor={entero(d.deudas.total)} />
                  <span className="chip">Pagas {entero(d.deudas.pago_del_mes)} al mes</span>
                </Panel>
              )}
            </div>
          )}

          {/* Hasta abajo: la lista de productos; cada renglón abre su mini resumen. */}
          {d.productos.length > 0 && (
            <Panel icono={Package} titulo="Tus productos que más te dejan" tema="productos" detalles="/productos" clase="panel-productos" indice={6} onPreguntar={preguntar}>
              <p className="pista-grafica"><MousePointerClick size={13} aria-hidden="true" /> Toca un producto para ver su resumen.</p>
              <div className="tabla-desplazable">
                <table className="tabla tabla-sencilla">
                  <thead><tr><th>Producto</th><th className="der">Vendiste</th><th className="der">Te dejó</th><th>¿Te queda?</th><th aria-hidden="true" /></tr></thead>
                  <tbody>
                    {d.productos.map((p) => (
                      <tr key={p.nombre} className="clic" tabIndex={0} aria-haspopup="dialog" aria-label={`${p.nombre}: ver resumen`}
                        onClick={() => setDetalle({ tipo: "producto", p })}
                        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setDetalle({ tipo: "producto", p }); } }}>
                        <td>{p.nombre}</td>
                        <td className="der num">{cantidad(p.vendiste, p.unidad)}</td>
                        <td className="der num"><strong>{entero(p.te_dejo)}</strong></td>
                        <td><span className={`semaforo ${p.inventario}`}>{INVENTARIO[p.inventario]}</span></td>
                        <td className="der muted" aria-hidden="true"><ChevronRight size={16} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}

      <AnimatePresence>
        {d && detalle && <DetalleSencillo key="detalle" d={d} x={detalle} onCerrar={() => setDetalle(null)} onClara={setTema} />}
      </AnimatePresence>

      {/* Clara siempre a la mano: botón flotante que abre su ventana de preguntas. */}
      <AnimatePresence>
        {!tema && !detalle && (
          <motion.button type="button" className="fab-chat" onClick={() => setTema(TEMAS.general)} aria-label="Pregúntale a Clara"
            initial={{ y: 80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 80, opacity: 0 }}
            whileHover={{ y: -3 }} whileTap={{ scale: 0.95 }} transition={{ type: "spring", stiffness: 260, damping: 22 }}>
            <span className="orbe"><Sparkles size={16} /></span>
            <span className="texto">Pregúntale a Clara</span>
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {tema && (
          <Suspense fallback={null}>
            <VentanaClara tema={tema} onCerrar={() => setTema(null)} />
          </Suspense>
        )}
      </AnimatePresence>
    </div>
  );
}
