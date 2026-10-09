import { AnimatePresence, motion } from "framer-motion";
import { ArrowDownUp, Award, Boxes, PackageSearch, Search, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EJE, Leyenda, SERIE, TooltipGrafica } from "../components/charts/comun";
import { Aviso, Semaforo, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { Pagina } from "../components/ui/Pagina";
import { usePeriodo } from "../context/Periodo";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { dinero, dineroCompacto, fechaCorta, numero, pct } from "../lib/formato";
import type { ProductoMetricas, Productos as TipoProductos, Pronostico, Semaforo as TipoSemaforo } from "../lib/tipos";

type Orden = "utilidad" | "ventas" | "margen_actual" | "dias_inventario" | "nombre";

function DetalleProducto({ p, idEmpresa, cerrar }: { p: ProductoMetricas; idEmpresa: number; cerrar: () => void }) {
  const fc = useApi<Pronostico>(`/empresas/${idEmpresa}/forecast`, { id_producto: p.id_producto, serie: "unidades", dias: 30 });
  const datos = useMemo(() => {
    if (!fc.datos) return [];
    const hist = fc.datos.historico.slice(-60).map((h) => ({ fecha: h.fecha, real: h.valor }));
    const fut = fc.datos.pronostico.map((f) => ({ fecha: f.fecha, estimado: f.valor, rango: [f.inferior, f.superior] as [number, number] }));
    return [...hist, ...fut];
  }, [fc.datos]);
  const sugerido = Math.max(0, Math.ceil(p.venta_diaria * 14 - p.stock_actual));

  return (
    <>
      <motion.div className="velo" style={{ zIndex: 65 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={cerrar} />
      <motion.aside className="cajon" role="dialog" aria-label={`Detalle de ${p.nombre}`} initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }}
        transition={{ type: "spring", stiffness: 320, damping: 34 }}>
        <header>
          <div className="pila" style={{ gap: 4 }}>
            <span className="eyebrow">{p.categoria}</span>
            <h2>{p.nombre}</h2>
            <Semaforo estado={p.semaforo} texto={p.dias_inventario !== null ? `${numero(p.dias_inventario)} días de inventario` : undefined} />
          </div>
          <button className="btn icono fantasma" onClick={cerrar} aria-label="Cerrar">
            <X size={18} />
          </button>
        </header>
        <div className="cuerpo">
          <div className="mini-kpis">
            {[
              ["Precio de venta", dinero(p.precio_venta)],
              ["Costo", dinero(p.costo_promedio)],
              ["Te deja por " + p.unidad, dinero(p.precio_venta - p.costo_promedio)],
              ["Margen actual", pct(p.margen_actual)],
              ["Existencia", `${numero(p.stock_actual)} ${p.unidad}`],
              ["Vendes al día", numero(p.venta_diaria)],
            ].map(([k, v], i) => (
              <motion.div key={k} className="mini-kpi" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.04 }}>
                <div className="k">{k}</div>
                <div className="v num">{v}</div>
              </motion.div>
            ))}
          </div>
          {p.semaforo !== "verde" && p.venta_diaria > 0 && (
            <Aviso>
              Para cubrir 2 semanas al ritmo actual te conviene comprar unas <strong>{numero(sugerido)} {p.unidad}</strong>.
            </Aviso>
          )}
          <div className="pila">
            <h3>Ventas diarias y estimación a 30 días</h3>
            <Leyenda items={[{ nombre: "Vendido", color: SERIE.ventas, tipo: "linea" }, { nombre: "Estimado (promedio móvil)", color: SERIE.ventas, tipo: "punteada" }]} />
            <div style={{ height: 220 }}>
              {fc.datos ? (
                <ResponsiveContainer>
                  <ComposedChart data={datos} margin={{ top: 6, right: 8, bottom: 0, left: -10 }}>
                    <CartesianGrid vertical={false} stroke="var(--grid)" />
                    <XAxis dataKey="fecha" {...EJE} tickFormatter={fechaCorta} minTickGap={40} />
                    <YAxis {...EJE} width={44} />
                    <Tooltip content={<TooltipGrafica formato={(v) => `${numero(v)} ${p.unidad}`} titulo={(l) => fechaCorta(String(l))}
                      nombres={{ real: "Vendido", estimado: "Estimado" }} />} />
                    <Area dataKey="rango" stroke="none" fill={SERIE.ventas} fillOpacity={0.12} isAnimationActive={false} name="_rango" />
                    <Line dataKey="real" stroke={SERIE.ventas} strokeWidth={2} dot={false} animationDuration={900} />
                    <Line dataKey="estimado" stroke={SERIE.ventas} strokeWidth={2} strokeDasharray="5 4" dot={false} animationDuration={900} />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <TarjetaCargando alto={180} />
              )}
            </div>
            <p className="mini muted justificado">
              Estimación simple con el promedio de los últimos 30 días. No considera temporadas; en la siguiente fase se usará un
              modelo estadístico (Prophet/ARIMA).
            </p>
          </div>
        </div>
      </motion.aside>
    </>
  );
}

export function Productos() {
  const { empresa } = useSesion();
  const { params } = usePeriodo();
  const id = empresa?.id_empresa;
  const listo = Boolean(id && empresa?.tiene_datos && params.desde);
  const pr = useApi<TipoProductos>(listo ? `/empresas/${id}/productos` : null, params);
  const [busqueda, setBusqueda] = useState("");
  const [categoria, setCategoria] = useState("");
  const [semaforo, setSemaforo] = useState<TipoSemaforo | "">("");
  const [orden, setOrden] = useState<{ campo: Orden; asc: boolean }>({ campo: "utilidad", asc: false });
  const [abierto, setAbierto] = useState<ProductoMetricas | null>(null);
  const tablaRef = useRef<HTMLDivElement>(null);

  const irALaTabla = () =>
    tablaRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  const datos = pr.datos;
  const categorias = useMemo(() => [...new Set(datos?.productos.map((p) => p.categoria))].sort(), [datos]);
  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    const lista = (datos?.productos ?? []).filter(
      (p) => (!q || p.nombre.toLowerCase().includes(q)) && (!categoria || p.categoria === categoria) && (!semaforo || p.semaforo === semaforo),
    );
    const { campo, asc } = orden;
    return [...lista].sort((a, b) => {
      const va = a[campo] ?? (asc ? Infinity : -Infinity);
      const vb = b[campo] ?? (asc ? Infinity : -Infinity);
      const r = typeof va === "string" ? va.localeCompare(String(vb)) : Number(va) - Number(vb);
      return asc ? r : -r;
    });
  }, [datos, busqueda, categoria, semaforo, orden]);

  const ordenarPor = (campo: Orden) => setOrden((o) => ({ campo, asc: o.campo === campo ? !o.asc : campo === "nombre" || campo === "dias_inventario" }));
  const Th = ({ campo, children, clase = "der" }: { campo: Orden; children: string; clase?: string }) => (
    <th className={clase} aria-sort={orden.campo === campo ? (orden.asc ? "ascending" : "descending") : "none"}>
      <button onClick={() => ordenarPor(campo)}>
        {children} <ArrowDownUp size={12} opacity={orden.campo === campo ? 1 : 0.35} />
      </button>
    </th>
  );

  return (
    <Pagina eyebrow="Productos" titulo="¿Qué producto te deja más?"
      descripcion="Ventas, costo y ganancia de cada producto, y el semáforo de tu inventario. Haz clic en un producto para ver su detalle y su estimación de ventas.">
      {pr.error && <Aviso tipo="error">{pr.error}</Aviso>}
      {!datos ? (
        <div className="grid grid-2">
          <TarjetaCargando />
          <TarjetaCargando />
        </div>
      ) : (
        <>
          <div className="grid grid-2">
            <Tarjeta>
              <TituloTarjeta icono={Award} titulo="Top 5 por ganancia" sub={datos.periodo.etiqueta} />
              <div style={{ height: 250 }}>
                <ResponsiveContainer>
                  <BarChart data={datos.top_utilidad} layout="vertical" margin={{ top: 0, right: 64, bottom: 0, left: 0 }}>
                    <CartesianGrid horizontal={false} stroke="var(--grid)" />
                    <XAxis type="number" {...EJE} tickFormatter={dineroCompacto} />
                    <YAxis type="category" dataKey="nombre" {...EJE} width={150} tick={{ fill: "var(--ink-2)", fontSize: 12 }} />
                    <Tooltip content={<TooltipGrafica nombres={{ utilidad: "Te dejó" }} titulo={(l) => String(l)} />} cursor={{ fill: "var(--surface-hover)" }} />
                    <Bar dataKey="utilidad" fill={SERIE.utilidad} radius={[0, 4, 4, 0]} maxBarSize={22} animationDuration={900}
                      label={{ position: "right", formatter: (v: unknown) => dineroCompacto(Number(v)), fill: "var(--ink-2)", fontSize: 12 }} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Tarjeta>
            <Tarjeta retraso={0.06}>
              <TituloTarjeta icono={Boxes} titulo="Semáforo de inventario" sub={`Valor de tu inventario: ${dinero(datos.inventario.valor_total)}`} />
              <div className="grid" style={{ gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: 10 }}>
                {(["rojo", "amarillo", "verde", "sin_movimiento"] as TipoSemaforo[]).map((s, i) => (
                  <motion.button key={s} className="card interactiva centrado" style={{ padding: 16, cursor: "pointer", alignItems: "center", gap: 8,
                    outline: semaforo === s ? "2px solid var(--celeste)" : undefined }}
                    onClick={() => { setSemaforo(semaforo === s ? "" : s); irALaTabla(); }} aria-pressed={semaforo === s}
                    initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 + i * 0.05 }} whileTap={{ scale: 0.97 }}>
                    <strong className="num" style={{ fontSize: "var(--fs-xl)" }}>{datos.inventario[s]}</strong>
                    <Semaforo estado={s} texto={{ rojo: "Por agotarse", amarillo: "Vigilar", verde: "Suficiente", sin_movimiento: "Sin ventas" }[s]} />
                  </motion.button>
                ))}
              </div>
              <p className="mini muted justificado">
                Rojo: se acaba en {numero(empresa?.umbrales.dias_inventario_bajo)} días o menos al ritmo de venta de los últimos 30 días.
                Amarillo: hasta el doble. Toca un recuadro para filtrar la tabla.
              </p>
            </Tarjeta>
          </div>

          <Tarjeta retraso={0.1} interactiva={false}>
            <div className="fila-entre envolver salto-tabla" ref={tablaRef}>
              <TituloTarjeta icono={PackageSearch} titulo="Todos tus productos" sub={`${filtrados.length} de ${datos.productos.length} productos`} />
              <div className="filtros">
                <div style={{ position: "relative" }}>
                  <Search size={16} style={{ position: "absolute", left: 12, top: 13, color: "var(--faint)" }} aria-hidden="true" />
                  <input className="input" style={{ paddingLeft: 36 }} placeholder="Buscar producto…" value={busqueda}
                    onChange={(e) => setBusqueda(e.target.value)} aria-label="Buscar producto" />
                </div>
                <select className="select" style={{ width: 190 }} value={categoria} onChange={(e) => setCategoria(e.target.value)} aria-label="Categoría">
                  <option value="">Todas las categorías</option>
                  {categorias.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="tabla-envoltura">
              <table className="tabla">
                <thead>
                  <tr>
                    <Th campo="nombre" clase="">Producto</Th>
                    <Th campo="ventas">Vendiste</Th>
                    <th className="der">Costo</th>
                    <Th campo="utilidad">Te dejó</Th>
                    <Th campo="margen_actual">Margen</Th>
                    <th className="der">Existencia</th>
                    <Th campo="dias_inventario" clase="cen">Inventario</Th>
                  </tr>
                </thead>
                <tbody>
                  <AnimatePresence initial={false}>
                    {filtrados.map((p, i) => (
                      <motion.tr key={p.id_producto} className="clic" onClick={() => setAbierto(p)} layout
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ delay: Math.min(i, 20) * 0.015 }}
                        tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setAbierto(p)}>
                        <td>
                          <strong style={{ fontWeight: 600 }}>{p.nombre}</strong>
                          <div className="mini muted">{p.categoria}</div>
                        </td>
                        <td className="der num">{dinero(p.ventas)}</td>
                        <td className="der num muted">{dinero(p.costo)}</td>
                        <td className="der num"><strong>{dinero(p.utilidad)}</strong></td>
                        <td className="der">
                          <span className="margen-celda num">
                            {pct(p.margen_actual)}
                            <span className="barra"><span style={{ width: `${Math.max(0, Math.min(1, p.margen_actual ?? 0)) * 100}%`,
                              background: (p.margen_actual ?? 0) < (empresa?.umbrales.margen_producto_bajo ?? 0.1) ? "var(--bad)" : "var(--celeste)" }} /></span>
                          </span>
                        </td>
                        <td className="der num">{numero(p.stock_actual)} <span className="mini muted">{p.unidad}</span></td>
                        <td className="cen">
                          <Semaforo estado={p.semaforo} texto={p.dias_inventario !== null ? `${numero(p.dias_inventario)} d` : undefined} />
                        </td>
                      </motion.tr>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>
          </Tarjeta>
        </>
      )}
      <AnimatePresence>{abierto && id && <DetalleProducto p={abierto} idEmpresa={id} cerrar={() => setAbierto(null)} />}</AnimatePresence>
    </Pagina>
  );
}
