import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  History,
  Loader2,
  Package,
  Receipt,
  ShoppingCart,
  Sparkles,
  Truck,
  Undo2,
  UploadCloud,
  Wand2,
  type LucideIcon,
} from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { Aviso, Segmentado, Tarjeta, TituloTarjeta } from "../components/ui/basicos";
import { Pagina } from "../components/ui/Pagina";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import { leerToken } from "../lib/api";
import type { Analisis, Importacion, Previsualizacion, ReporteCarga, TipoDatos } from "../lib/tipos";

const TIPOS: { tipo: TipoDatos; titulo: string; texto: string; icono: LucideIcon }[] = [
  { tipo: "productos", titulo: "Productos", texto: "Tu catálogo: precio, costo y existencias de hoy.", icono: Package },
  { tipo: "ventas", titulo: "Ventas", texto: "Qué vendiste, cuándo, cuántas piezas y a qué precio.", icono: ShoppingCart },
  { tipo: "compras", titulo: "Compras", texto: "Lo que le compraste a tus proveedores.", icono: Truck },
  { tipo: "gastos", titulo: "Gastos", texto: "Renta, luz, sueldos, bolsas, fletes…", icono: Receipt },
];

const EJEMPLOS: Record<TipoDatos, string[][]> = {
  productos: [["Producto", "Categoría", "Precio de venta", "Costo", "Existencia"], ["Cuaderno raya", "Cuadernos", "45", "24", "40"], ["Pluma BIC azul", "Escritura", "8", "3.50", "120"]],
  ventas: [["Fecha", "Producto", "Cantidad", "Precio unitario"], ["15/09/2026", "Cuaderno raya", "3", "45"], ["15/09/2026", "Pluma BIC azul", "5", "8"]],
  compras: [["Fecha", "Producto", "Cantidad", "Costo unitario", "Proveedor"], ["10/09/2026", "Cuaderno raya", "50", "24", "Papelera"], ["12/09/2026", "Pluma BIC azul", "200", "3.50", "Papelera"]],
  gastos: [["Fecha", "Concepto", "Monto", "Tipo"], ["01/09/2026", "Renta del local", "1,200", "fijo"], ["05/09/2026", "Bolsas", "85.50", "variable"]],
};

const PASOS_TUTORIAL = [
  { titulo: "Empieza por tus productos", texto: "Sube primero tu catálogo con lo que tienes hoy en existencia. Así el semáforo de inventario sabe cuánto te queda de cada cosa. Si no tienes catálogo, no pasa nada: los productos se crean solos al subir tus ventas." },
  { titulo: "Prepara tu Excel como lo tengas", texto: "No necesitas un formato especial. Puede tener títulos arriba, filas de totales o columnas con otros nombres como “P. Unitario” o “Importe”. Lo importante es una fila por venta (o compra, o gasto) y una columna por dato." },
  { titulo: "Revisa cómo entendimos tus columnas", texto: "La IA local propone a qué corresponde cada columna usando solo los encabezados y unas filas de muestra. Tú decides: puedes cambiar cualquier columna antes de cargar." },
  { titulo: "Confirma y revisa el reporte", texto: "Te diremos cuántas filas se cargaron y, si alguna tuvo un problema, en qué fila de tu Excel está y por qué. Nada se guarda sin tu confirmación y puedes deshacer cualquier carga desde el historial." },
];

function HojaEjemplo({ filas }: { filas: string[][] }) {
  return (
    <div className="hoja-ejemplo" role="table" aria-label="Ejemplo de hoja de Excel">
      <table>
        <thead>
          <tr>
            <th className="col-letra" style={{ background: "var(--surface-2)", color: "var(--faint)", width: 28 }} />
            {filas[0].map((_, i) => (
              <th key={i} className="col-letra" style={{ background: "var(--surface-2)", color: "var(--faint)", textAlign: "center" }}>
                {String.fromCharCode(65 + i)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={i}>
              <td className="col-letra">{i + 1}</td>
              {f.map((c, j) => (i === 0 ? <th key={j}>{c}</th> : <td key={j} className="num">{c}</td>))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function descargarPlantilla(tipo: TipoDatos) {
  const r = await fetch(`/api/importar/plantillas/${tipo}`, { headers: { Authorization: `Bearer ${leerToken() ?? ""}` } });
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `plantilla_${tipo}.xlsx`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function Tutorial({ irASubir }: { irASubir: () => void }) {
  const [tipo, setTipo] = useState<TipoDatos>("ventas");
  return (
    <div className="grid grid-lateral">
      <Tarjeta>
        <TituloTarjeta icono={BookOpen} titulo="Cómo pasar tus datos de Excel a Cuentas Claras" sub="4 pasos, unos 5 minutos" />
        <div className="pila" style={{ gap: 22 }}>
          {PASOS_TUTORIAL.map((p, i) => (
            <motion.div key={p.titulo} className="tutorial-paso" initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 + i * 0.12 }}>
              <motion.span className="num-paso" whileHover={{ rotate: -6, scale: 1.05 }}>{i + 1}</motion.span>
              <div className="pila" style={{ gap: 4 }}>
                <h3>{p.titulo}</h3>
                <p className="justificado pequeno" style={{ color: "var(--ink-2)" }}>{p.texto}</p>
              </div>
            </motion.div>
          ))}
        </div>
        <div className="fila envolver">
          <button className="btn primario" onClick={irASubir}>
            <UploadCloud size={16} /> Subir mi archivo
          </button>
        </div>
      </Tarjeta>
      <Tarjeta retraso={0.1}>
        <TituloTarjeta icono={FileSpreadsheet} titulo="Así se ve un archivo listo" sub="Elige el tipo de datos" />
        <Segmentado<TipoDatos> etiqueta="Tipo de datos" valor={tipo} onChange={setTipo}
          opciones={TIPOS.map((t) => ({ valor: t.tipo, texto: t.titulo }))} />
        <AnimatePresence mode="wait">
          <motion.div key={tipo} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25 }}>
            <HojaEjemplo filas={EJEMPLOS[tipo]} />
          </motion.div>
        </AnimatePresence>
        <ul className="pequeno justificado" style={{ margin: 0, paddingLeft: 18, color: "var(--ink-2)", display: "grid", gap: 6 }}>
          <li>Fechas como día/mes/año (15/09/2026). También entiendo 2026-09-15 o “15 sep 2026”.</li>
          <li>Montos con o sin “$” y comas: $1,250.00, 1250 o 1.250,00.</li>
          <li>Si no tienes precio unitario pero sí el total, lo calculo por ti.</li>
          <li>En gastos, si no pones el tipo, deduzco si es fijo (renta, luz, sueldo) o variable.</li>
        </ul>
        <button className="btn" onClick={() => descargarPlantilla(tipo)}>
          <Download size={16} /> Descargar plantilla de {TIPOS.find((t) => t.tipo === tipo)?.titulo.toLowerCase()}
        </button>
      </Tarjeta>
    </div>
  );
}

const NOMBRES_PASOS = ["Tipo", "Archivo", "Columnas", "Revisión", "Listo"];

function Asistente({ alTerminar }: { alTerminar: () => void }) {
  const { empresa, recargarEmpresa } = useSesion();
  const [paso, setPaso] = useState(0);
  const [tipo, setTipo] = useState<TipoDatos | null>(null);
  const [analisis, setAnalisis] = useState<Analisis | null>(null);
  const [mapeo, setMapeo] = useState<Record<string, string | null>>({});
  const [vista, setVista] = useState<Previsualizacion | null>(null);
  const [reporte, setReporte] = useState<ReporteCarga | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [encima, setEncima] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const id = empresa?.id_empresa;

  const ejecutar = async (texto: string, fn: () => Promise<void>) => {
    setOcupado(texto);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setOcupado(null);
    }
  };

  const subir = (archivo: File) =>
    ejecutar("Leyendo tu archivo y proponiendo columnas…", async () => {
      const datos = new FormData();
      datos.append("archivo", archivo);
      datos.append("tipo_datos", tipo!);
      const a = await api.subir<Analisis>(`/empresas/${id}/importaciones/analizar`, datos);
      setAnalisis(a);
      setMapeo(Object.fromEntries(a.mapeo.map((m) => [m.columna, m.campo])));
      setPaso(2);
    });

  const previsualizar = () =>
    ejecutar("Revisando fila por fila…", async () => {
      setVista(await api.post<Previsualizacion>(`/empresas/${id}/importaciones/${analisis!.token}/previsualizar`, { mapeo }));
      setPaso(3);
    });

  const confirmar = () =>
    ejecutar("Guardando en tu base de datos…", async () => {
      setReporte(await api.post<ReporteCarga>(`/empresas/${id}/importaciones/${analisis!.token}/confirmar`, { mapeo }));
      setPaso(4);
      await recargarEmpresa();
      alTerminar();
    });

  const soltar = (e: DragEvent) => {
    e.preventDefault();
    setEncima(false);
    const f = e.dataTransfer.files?.[0];
    if (f) subir(f);
  };

  const asignados = new Set(Object.values(mapeo).filter(Boolean));
  const faltan = analisis?.campos.filter((c) => c.requerido && !asignados.has(c.clave)) ?? [];
  const sinPrecio = analisis && ((tipo === "ventas" && !asignados.has("precio_unitario") && !asignados.has("total")) ||
    (tipo === "compras" && !asignados.has("costo_unitario") && !asignados.has("total")));
  const reiniciar = () => {
    setPaso(0); setTipo(null); setAnalisis(null); setVista(null); setReporte(null); setError(null);
  };

  return (
    <Tarjeta interactiva={false}>
      <div className="pasos" aria-label="Progreso">
        {NOMBRES_PASOS.map((n, i) => (
          <span key={n} className="fila" style={{ gap: 6 }}>
            <span className={`paso ${i === paso ? "activo" : i < paso ? "hecho" : ""}`}>
              <span className="n">{i < paso ? <CheckCircle2 size={14} /> : i + 1}</span>
              {n}
            </span>
            {i < NOMBRES_PASOS.length - 1 && <span className="paso-linea" />}
          </span>
        ))}
      </div>

      {error && <Aviso tipo="error">{error}</Aviso>}

      <AnimatePresence mode="wait">
        <motion.div key={paso} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="pila" style={{ gap: 18 }}>
          {paso === 0 && (
            <>
              <h3>¿Qué vas a subir?</h3>
              <div className="tipos-datos">
                {TIPOS.map((t) => (
                  <motion.button key={t.tipo} className="tipo-dato" aria-pressed={tipo === t.tipo} onClick={() => setTipo(t.tipo)} whileHover={{ y: -3 }} whileTap={{ scale: 0.98 }}>
                    <span className="ic"><t.icono size={19} /></span>
                    <strong>{t.titulo}</strong>
                    <p>{t.texto}</p>
                  </motion.button>
                ))}
              </div>
              <div className="fila">
                <button className="btn primario" disabled={!tipo} onClick={() => setPaso(1)}>
                  Continuar <ArrowRight size={16} />
                </button>
              </div>
            </>
          )}

          {paso === 1 && (
            <>
              <div className={`zona-archivo ${encima ? "encima" : ""}`} onClick={() => input.current?.click()} onDragOver={(e) => { e.preventDefault(); setEncima(true); }}
                onDragLeave={() => setEncima(false)} onDrop={soltar} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
                aria-label="Elegir archivo de Excel o CSV">
                {ocupado ? (
                  <>
                    <Loader2 size={40} className="girando" color="var(--celeste)" />
                    <strong>{ocupado}</strong>
                    <span className="pequeno muted">La IA local revisa solo tus encabezados y 5 filas de muestra.</span>
                  </>
                ) : (
                  <>
                    <motion.div animate={{ y: encima ? -8 : [0, -6, 0] }} transition={encima ? {} : { duration: 2.4, repeat: Infinity }}>
                      <UploadCloud size={44} color="var(--celeste)" />
                    </motion.div>
                    <strong>Arrastra aquí tu archivo de {TIPOS.find((t) => t.tipo === tipo)?.titulo.toLowerCase()}</strong>
                    <span className="pequeno muted">o haz clic para elegirlo · .xlsx o .csv · máximo 5 MB</span>
                  </>
                )}
                <input ref={input} type="file" hidden accept=".xlsx,.csv" onChange={(e) => e.target.files?.[0] && subir(e.target.files[0])} />
              </div>
              <div className="fila-entre envolver">
                <button className="btn fantasma" onClick={() => setPaso(0)}><ArrowLeft size={16} /> Atrás</button>
                <button className="btn" onClick={() => descargarPlantilla(tipo!)}><Download size={16} /> ¿No tienes formato? Descarga la plantilla</button>
              </div>
            </>
          )}

          {paso === 2 && analisis && (
            <>
              <div className="fila-entre envolver">
                <div className="pila" style={{ gap: 4 }}>
                  <h3>¿Así entendimos bien tus columnas?</h3>
                  <span className="pequeno muted">{analisis.nombre_archivo} · {analisis.filas} filas · encabezados en la fila {analisis.fila_encabezado}</span>
                </div>
                <span className={`chip ${analisis.uso_ia ? "celeste" : ""}`}>
                  <Wand2 size={12} /> {analisis.uso_ia ? "Propuesta con IA local + reglas" : "Propuesta con reglas (IA apagada)"}
                </span>
              </div>
              {analisis.advertencias.map((a) => <Aviso key={a}>{a}</Aviso>)}
              <div className="tabla-envoltura">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Tu columna</th>
                      <th>Ejemplos</th>
                      <th>Corresponde a</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analisis.columnas.map((c, i) => {
                      const sugerida = analisis.mapeo.find((m) => m.columna === c.nombre);
                      return (
                        <motion.tr key={c.nombre} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                          <td>
                            <strong>{c.nombre}</strong>
                            <div className="mini muted">{c.tipo_detectado}{c.vacios ? ` · ${c.vacios} vacías` : ""}</div>
                          </td>
                          <td className="pequeno muted" style={{ maxWidth: 260 }}>{c.muestra.join(" · ") || "—"}</td>
                          <td>
                            <div className="fila" style={{ gap: 8 }}>
                              <select className="select" style={{ height: 36, minWidth: 180 }} value={mapeo[c.nombre] ?? ""} aria-label={`Campo para ${c.nombre}`}
                                onChange={(e) => setMapeo({ ...mapeo, [c.nombre]: e.target.value || null })}>
                                <option value="">— No usar —</option>
                                {analisis.campos.map((campo) => (
                                  <option key={campo.clave} value={campo.clave} disabled={asignados.has(campo.clave) && mapeo[c.nombre] !== campo.clave}>
                                    {campo.etiqueta}{campo.requerido ? " *" : ""}
                                  </option>
                                ))}
                              </select>
                              {sugerida?.fuente === "ia" && mapeo[c.nombre] === sugerida.campo && (
                                <span className="chip celeste" title="Propuesto por la IA"><Sparkles size={11} /> IA</span>
                              )}
                            </div>
                          </td>
                        </motion.tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {(faltan.length > 0 || sinPrecio) && (
                <Aviso tipo="error">
                  Falta indicar: {[...faltan.map((f) => f.etiqueta), ...(sinPrecio ? [tipo === "ventas" ? "Precio unitario o Total" : "Costo unitario o Total"] : [])].join(", ")}.
                </Aviso>
              )}
              <div className="fila-entre envolver">
                <button className="btn fantasma" onClick={() => setPaso(1)}><ArrowLeft size={16} /> Otro archivo</button>
                <button className="btn primario" disabled={faltan.length > 0 || !!sinPrecio || !!ocupado} onClick={previsualizar}>
                  {ocupado ? <Loader2 size={16} className="girando" /> : <ArrowRight size={16} />} Revisar datos
                </button>
              </div>
            </>
          )}

          {paso === 3 && vista && (
            <>
              <div className="grid grid-3">
                <div className="mini-kpi"><div className="k">Filas listas</div><div className="v num" style={{ color: "var(--ok-ink)" }}>{vista.filas_ok}</div></div>
                <div className="mini-kpi"><div className="k">Filas con problema</div><div className="v num" style={{ color: vista.filas_con_error ? "var(--bad-ink)" : undefined }}>{vista.filas_con_error}</div></div>
                <div className="mini-kpi"><div className="k">Tipo</div><div className="v">{TIPOS.find((t) => t.tipo === tipo)?.titulo}</div></div>
              </div>
              {vista.advertencias.map((a) => <Aviso key={a}>{a}</Aviso>)}
              {vista.errores.length > 0 && (
                <div className="pila" style={{ gap: 6 }}>
                  <h4>Estas filas no se cargarán (corrígelas en tu Excel y vuelve a subirlas):</h4>
                  <div className="pila" style={{ gap: 4, maxHeight: 180, overflowY: "auto" }}>
                    {vista.errores.map((e) => (
                      <span key={e.fila} className="pequeno"><span className="chip bad">Fila {e.fila}</span> {e.motivo}</span>
                    ))}
                  </div>
                </div>
              )}
              {vista.muestra.length > 0 && (
                <div className="tabla-envoltura">
                  <table className="tabla">
                    <thead><tr>{Object.keys(vista.muestra[0]).filter((k) => k !== "_fila").map((k) => <th key={k}>{k.replace("_", " ")}</th>)}</tr></thead>
                    <tbody>
                      {vista.muestra.map((f, i) => (
                        <tr key={i}>{Object.entries(f).filter(([k]) => k !== "_fila").map(([k, v]) => <td key={k} className="num">{v.replace("T00:00:00", "")}</td>)}</tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="fila-entre envolver">
                <button className="btn fantasma" onClick={() => setPaso(2)}><ArrowLeft size={16} /> Ajustar columnas</button>
                <button className="btn primario" disabled={!vista.filas_ok || !!ocupado} onClick={confirmar}>
                  {ocupado ? <Loader2 size={16} className="girando" /> : <CheckCircle2 size={16} />} Cargar {vista.filas_ok} filas
                </button>
              </div>
            </>
          )}

          {paso === 4 && reporte && (
            <div className="pila centrado" style={{ alignItems: "center", padding: "12px 0" }}>
              <motion.div initial={{ scale: 0, rotate: -30 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 260, damping: 14 }}>
                <CheckCircle2 size={64} color="var(--ok)" />
              </motion.div>
              <h2 className="centrado">¡Listo! Cargamos {reporte.filas_ok} filas</h2>
              <p className="muted justificado" style={{ maxWidth: 520 }}>
                {reporte.filas_con_error > 0 ? `${reporte.filas_con_error} filas tuvieron problemas y no se cargaron. ` : ""}
                {reporte.productos_creados.length > 0 ? `Se crearon ${reporte.productos_creados.length} productos nuevos. ` : ""}
                {reporte.productos_actualizados > 0 ? `Se actualizaron ${reporte.productos_actualizados} productos. ` : ""}
                Tu panel ya incluye estos datos. Si algo no cuadra, puedes deshacer esta carga en el historial.
              </p>
              <button className="btn primario" onClick={reiniciar}><UploadCloud size={16} /> Subir otro archivo</button>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </Tarjeta>
  );
}

function Historial({ version }: { version: number }) {
  const { empresa, recargarEmpresa } = useSesion();
  const h = useApi<Importacion[]>(empresa ? `/empresas/${empresa.id_empresa}/importaciones` : null, { v: version });
  const [deshaciendo, setDeshaciendo] = useState<number | null>(null);
  const deshacer = async (imp: Importacion) => {
    if (!window.confirm(`¿Deshacer la carga de "${imp.nombre_archivo}"? Se borrarán sus ${imp.filas_ok} filas.`)) return;
    setDeshaciendo(imp.id_importacion);
    try {
      await api.delete(`/empresas/${empresa!.id_empresa}/importaciones/${imp.id_importacion}`);
      h.recargar();
      await recargarEmpresa();
    } finally {
      setDeshaciendo(null);
    }
  };
  return (
    <Tarjeta retraso={0.1}>
      <TituloTarjeta icono={History} titulo="Historial de importaciones" sub="Cada carga queda registrada y se puede deshacer" />
      {!h.datos?.length ? (
        <p className="muted pequeno">Aún no has subido archivos. Los datos de demostración se cargaron directamente en la base.</p>
      ) : (
        <div className="tabla-envoltura">
          <table className="tabla">
            <thead><tr><th>Archivo</th><th>Tipo</th><th>Fecha</th><th className="der">Filas</th><th className="cen">Estado</th><th /></tr></thead>
            <tbody>
              {h.datos.map((imp) => (
                <tr key={imp.id_importacion}>
                  <td><strong style={{ fontWeight: 600 }}>{imp.nombre_archivo}</strong></td>
                  <td className="pequeno">{imp.tipo_datos}</td>
                  <td className="pequeno muted">{new Date(imp.fecha).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" })}</td>
                  <td className="der num">{imp.filas_ok}{imp.filas_con_error ? <span className="muted"> (+{imp.filas_con_error} con error)</span> : null}</td>
                  <td className="cen">
                    <span className={`chip ${imp.estado === "completada" ? "ok" : imp.estado === "con_errores" ? "warn" : ""}`}>
                      {imp.estado === "completada" ? "Completa" : imp.estado === "con_errores" ? "Con errores" : "Deshecha"}
                    </span>
                  </td>
                  <td className="der">
                    {imp.estado !== "deshecha" && (
                      <button className="btn chico fantasma peligro" onClick={() => deshacer(imp)} disabled={deshaciendo === imp.id_importacion}>
                        {deshaciendo === imp.id_importacion ? <Loader2 size={14} className="girando" /> : <Undo2 size={14} />} Deshacer
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Tarjeta>
  );
}

export function Importar() {
  const { empresa } = useSesion();
  const [vista, setVista] = useState<"tutorial" | "subir">(empresa?.tiene_datos ? "subir" : "tutorial");
  const [version, setVersion] = useState(0);
  return (
    <Pagina titulo="Importar datos"
      descripcion="Carga ventas, productos, compras y gastos desde archivos Excel (.xlsx) o CSV. Si es tu primera vez, revisa el tutorial."
      acciones={<Segmentado etiqueta="Vista" valor={vista} onChange={setVista} opciones={[{ valor: "tutorial", texto: "Tutorial" }, { valor: "subir", texto: "Subir archivo" }]} />}>
      {empresa && !empresa.tiene_datos && vista === "tutorial" && (
        <Aviso>Bienvenido a {empresa.nombre_negocio}. Tu panel está vacío: sigue estos pasos para cargar tus primeros datos.</Aviso>
      )}
      <AnimatePresence mode="wait">
        <motion.div key={vista} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="pila" style={{ gap: "var(--sp-5)" }}>
          {vista === "tutorial" ? <Tutorial irASubir={() => setVista("subir")} /> : <Asistente alTerminar={() => setVersion((v) => v + 1)} />}
        </motion.div>
      </AnimatePresence>
      <Historial version={version} />
    </Pagina>
  );
}
