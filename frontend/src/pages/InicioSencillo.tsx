import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle, ArrowRight, CheckCircle2, CircleHelp, CreditCard, FileSpreadsheet, Landmark, OctagonAlert, Package,
  ShoppingBasket, Sparkles, TrendingUp, type LucideIcon,
} from "lucide-react";
import { lazy, Suspense, useState, type ReactNode } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Link } from "react-router-dom";
import { TooltipGrafica } from "../components/charts/comun";
import type { TemaClara } from "../components/sencillo/VentanaClara";
import { Aviso, Esqueleto } from "../components/ui/basicos";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { dinero, dineroCompacto, fechaLarga, numero } from "../lib/formato";
import type { Estado3, Inicio, Semaforo } from "../lib/tipos";

// La ventana (con su lector de Markdown) se descarga la primera vez que alguien toca "¿Qué es esto?".
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

// "¿Qué es esto?" de cada tarjeta: escrito por personas, en palabras de todos los días.
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

function TarjetaSencilla({ icono: Icono, titulo, tema, detalles, children, onPreguntar }: {
  icono: LucideIcon; titulo: string; tema: string; detalles: string; children: ReactNode; onPreguntar: (tema: string) => void;
}) {
  return (
    <motion.section className="tarjeta-sencilla" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <h2><span className="icono-sencillo" aria-hidden="true"><Icono size={22} /></span>{titulo}</h2>
      {children}
      <div className="acciones-sencillas">
        <button type="button" className="btn grande" onClick={() => onPreguntar(tema)}>
          <CircleHelp size={20} /> ¿Qué es esto?
        </button>
        <Link to={detalles} className="btn grande fantasma">
          Ver detalles <ArrowRight size={20} />
        </Link>
      </div>
    </motion.section>
  );
}

function GraficaVentas({ meses }: { meses: Inicio["ventas_por_mes"] }) {
  const actual = meses[meses.length - 1];
  const anterior = meses[meses.length - 2];
  return (
    <>
      {actual && (
        <p className="frase-sencilla">
          En <strong>{actual.etiqueta.toLowerCase()}</strong> vendiste <strong>{entero(actual.ventas)}</strong>
          {anterior && <>. En {anterior.etiqueta.toLowerCase()} habías vendido {entero(anterior.ventas)}</>}.
        </p>
      )}
      <div style={{ height: 220 }} role="img"
        aria-label={`Ventas por mes: ${meses.map((m) => `${m.etiqueta} ${entero(m.ventas)}`).join(", ")}`}>
        <ResponsiveContainer>
          <BarChart data={meses} margin={{ top: 28, right: 4, bottom: 0, left: 4 }}>
            <XAxis dataKey="etiqueta" axisLine={false} tickLine={false} tick={{ fill: "var(--ink-2)", fontSize: 15, fontWeight: 600 }} />
            <Tooltip content={<TooltipGrafica nombres={{ ventas: "Vendiste" }} />} cursor={{ fill: "var(--surface-hover)" }} />
            <Bar dataKey="ventas" radius={[4, 4, 0, 0]} maxBarSize={56} animationDuration={700}>
              {meses.map((m) => (
                <Cell key={m.etiqueta} fill={m.actual ? "var(--s1)" : "color-mix(in srgb, var(--s1) 40%, var(--surface))"} />
              ))}
              <LabelList dataKey="ventas" position="top" formatter={(v) => dineroCompacto(Number(v))}
                style={{ fill: "var(--ink-2)", fontSize: 13, fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

export function InicioSencillo() {
  const { usuario, empresa, empresas } = useSesion();
  const id = empresa?.id_empresa;
  const inicio = useApi<Inicio>(id ? `/empresas/${id}/inicio` : null);
  const [tema, setTema] = useState<string | null>(null);
  const d = inicio.datos;
  const esDueno = empresas.find((e) => e.id_empresa === id)?.rol === "dueno";
  const nombre = usuario?.nombre.split(" ")[0] ?? "";

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
  return (
    <div className="inicio-sencillo">
      <div className="saludo-sencillo">
        <h1>Hola, {nombre}</h1>
        <button type="button" className="btn grande primario boton-clara" onClick={() => setTema("general")}>
          <Sparkles size={22} /> Pregúntale a Clara
        </button>
      </div>
      {inicio.error && <Aviso tipo="error">{inicio.error}</Aviso>}

      {!d ? (
        [0, 1, 2].map((i) => <div key={i} className="tarjeta-sencilla"><Esqueleto alto={26} ancho="50%" /><Esqueleto alto={90} /></div>)
      ) : (
        <>
          {c && (
            <TarjetaSencilla icono={TrendingUp} titulo={`¿Cómo te fue en ${c.mes}?`} tema="como_te_fue" detalles="/resumen" onPreguntar={setTema}>
              <p className={`estado-sencillo ${c.estado}`}>
                {(() => { const { Icono, texto } = ESTADO[c.estado]; return <><Icono size={22} aria-hidden="true" /> {texto}</>; })()}
              </p>
              <p className="frase-sencilla">{c.frase}</p>
              <div className="cuenta-sencilla" aria-label={`Vendiste ${entero(c.ventas)}, gastaste ${entero(c.gastaste)}, te quedó ${entero(c.te_quedo)}`}>
                <div><span>Vendiste</span><strong>{entero(c.ventas)}</strong></div>
                <span className="signo" aria-hidden="true">−</span>
                <div><span>Gastaste</span><strong>{entero(c.gastaste)}</strong></div>
                <span className="signo" aria-hidden="true">=</span>
                <div className={`resultado ${c.te_quedo < 0 ? "negativo" : ""}`}><span>{c.te_quedo < 0 ? "Perdiste" : "Te quedó"}</span><strong>{entero(Math.abs(c.te_quedo))}</strong></div>
              </div>
            </TarjetaSencilla>
          )}

          {d.ventas_por_mes.length > 0 && (
            <TarjetaSencilla icono={TrendingUp} titulo="¿Vendes más o menos que antes?" tema="ventas" detalles="/finanzas" onPreguntar={setTema}>
              <GraficaVentas meses={d.ventas_por_mes} />
            </TarjetaSencilla>
          )}

          {d.productos.length > 0 && (
            <TarjetaSencilla icono={Package} titulo="Tus productos que más te dejan" tema="productos" detalles="/productos" onPreguntar={setTema}>
              <div className="tabla-envoltura">
                <table className="tabla tabla-sencilla">
                  <thead><tr><th>Producto</th><th className="der">Vendiste</th><th className="der">Te dejó</th><th>¿Te queda?</th></tr></thead>
                  <tbody>
                    {d.productos.map((p) => (
                      <tr key={p.nombre}>
                        <td>{p.nombre}</td>
                        <td className="der num">{cantidad(p.vendiste, p.unidad)}</td>
                        <td className="der num"><strong>{entero(p.te_dejo)}</strong></td>
                        <td><span className={`semaforo ${p.inventario}`}>{INVENTARIO[p.inventario]}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TarjetaSencilla>
          )}

          {v && (
            <TarjetaSencilla icono={ShoppingBasket} titulo={`Lo que viene en ${v.mes}`} tema="lo_que_viene" detalles="/proyecciones" onPreguntar={setTema}>
              <ul className="lista-sencilla">
                <li>Vas a vender cerca de <strong>{entero(v.ventas_esperadas)}</strong> y te quedarían unos <strong>{entero(v.ganancia_esperada)}</strong>.</li>
                <li className={v.te_alcanza ? "bien" : "mal"}>
                  {v.te_alcanza ? <CheckCircle2 size={22} aria-hidden="true" /> : <OctagonAlert size={22} aria-hidden="true" />}
                  <span>
                    <strong>{v.te_alcanza ? "Sí te alcanza el dinero." : "Cuidado: te podría faltar dinero."}</strong>{" "}
                    {v.te_alcanza
                      ? `Hoy tienes ${entero(v.efectivo_hoy)} y a fin de mes tendrías unos ${entero(v.efectivo_fin_de_mes)}.`
                      : `El ${fechaLarga(v.fecha_riesgo ?? "")} podrías quedarte con muy poco. Hoy tienes ${entero(v.efectivo_hoy)}.`}
                  </span>
                </li>
              </ul>
              {v.comprar.length > 0 ? (
                <div className="compras-sencillas">
                  <h3>Compra pronto:</h3>
                  <ul>
                    {v.comprar.map((p) => (
                      <li key={p.nombre}><span>{p.nombre}</span><span className="num">{cantidad(p.cantidad, p.unidad)} · {entero(p.costo)}</span></li>
                    ))}
                  </ul>
                  <p className="muted">En total, unos <strong>{entero(v.total_compra)}</strong>.</p>
                </div>
              ) : (
                <p className="frase-sencilla">Por ahora no necesitas comprar mercancía.</p>
              )}
            </TarjetaSencilla>
          )}

          {(d.impuestos || d.deudas) && (
            <div className="mini-sencillas">
              {d.impuestos && (
                <TarjetaSencilla icono={Landmark} titulo="Impuestos" tema="impuestos" detalles="/impuestos" onPreguntar={setTema}>
                  {d.impuestos.a_pagar > 0 ? (
                    <p className="frase-sencilla">
                      Por {d.impuestos.mes.toLowerCase()} le toca pagar al SAT <strong>{entero(d.impuestos.a_pagar)}</strong>.
                      Tienes hasta el <strong>{fechaLarga(d.impuestos.fecha_limite)}</strong>.
                    </p>
                  ) : (
                    <p className="frase-sencilla">Por {d.impuestos.mes.toLowerCase()} no te toca pagar al SAT.</p>
                  )}
                </TarjetaSencilla>
              )}
              {d.deudas && (
                <TarjetaSencilla icono={CreditCard} titulo="Deudas" tema="deudas" detalles="/deudas" onPreguntar={setTema}>
                  <p className="frase-sencilla">
                    Debes <strong>{entero(d.deudas.total)}</strong> en total. Al mes pagas unos <strong>{entero(d.deudas.pago_del_mes)}</strong>.
                  </p>
                  {d.deudas.paga_primero && <p className="frase-sencilla">Si te sobra dinero, abona primero a <strong>{d.deudas.paga_primero}</strong>.</p>}
                </TarjetaSencilla>
              )}
            </div>
          )}
        </>
      )}

      <AnimatePresence>
        {tema && (
          <Suspense fallback={null}>
            <VentanaClara tema={TEMAS[tema]} onCerrar={() => setTema(null)} />
          </Suspense>
        )}
      </AnimatePresence>
    </div>
  );
}
