import { AnimatePresence } from "framer-motion";
import { Loader2, RotateCcw, Save, SlidersHorizontal, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { TarjetaAlerta } from "../components/AlertaTarjeta";
import { Aviso, EstadoVacio, Segmentado, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { Pagina } from "../components/ui/Pagina";
import { useAlertas } from "../context/Alertas";
import { usePeriodo } from "../context/Periodo";
import { useSesion } from "../context/Sesion";
import { api } from "../lib/api";
import type { Alerta, NivelAlerta, Umbrales } from "../lib/tipos";

const CONTROLES: { clave: keyof Umbrales; texto: string; min: number; max: number; paso: number; unidad: "%" | "días" }[] = [
  { clave: "margen_neto_bajo", texto: "🔴 Margen del negocio bajo si es menor a", min: 0.05, max: 0.5, paso: 0.01, unidad: "%" },
  { clave: "margen_producto_bajo", texto: "🔴 Producto con margen muy bajo si es menor a", min: 0.02, max: 0.4, paso: 0.01, unidad: "%" },
  { clave: "dias_inventario_bajo", texto: "🔴 Producto por agotarse si le quedan", min: 1, max: 30, paso: 1, unidad: "días" },
  { clave: "caida_ventas", texto: "🟡 Avisar si las ventas caen más de", min: 0.02, max: 0.5, paso: 0.01, unidad: "%" },
  { clave: "gastos_vs_ventas_pp", texto: "🟡 Avisar si los gastos crecen por encima de las ventas más de", min: 0.01, max: 0.3, paso: 0.01, unidad: "%" },
  { clave: "subida_costo", texto: "🟡 Avisar si el costo de un producto sube más de", min: 0.01, max: 0.3, paso: 0.01, unidad: "%" },
  { clave: "buena_rentabilidad", texto: "🟢 Felicitar si el margen supera", min: 0.1, max: 0.7, paso: 0.01, unidad: "%" },
];

function PanelUmbrales({ alGuardar }: { alGuardar: () => void }) {
  const { empresa, empresas, recargarEmpresa } = useSesion();
  const [valores, setValores] = useState<Umbrales | null>(empresa?.umbrales ?? null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setValores(empresa?.umbrales ?? null), [empresa?.umbrales]);
  if (!valores || !empresa) return null;
  const soloLectura = empresas.find((e) => e.id_empresa === empresa.id_empresa)?.rol === "consulta";

  const guardar = async () => {
    setGuardando(true);
    setError(null);
    try {
      await api.put(`/empresas/${empresa.id_empresa}/umbrales`, valores);
      await recargarEmpresa();
      alGuardar();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Tarjeta retraso={0.1}>
      <TituloTarjeta icono={SlidersHorizontal} titulo="¿Cuándo quieres que te avise?" sub="Ajusta los umbrales a tu tipo de negocio" />
      <div className="pila" style={{ gap: 16 }}>
        {CONTROLES.map((c) => {
          const v = valores[c.clave];
          return (
            <div key={c.clave} className="pila" style={{ gap: 6 }}>
              <label htmlFor={c.clave} className="fila-entre pequeno">
                <span>{c.texto}</span>
                <strong className="num chip celeste">{c.unidad === "%" ? `${Math.round(v * 100)}%` : `${v} días`}</strong>
              </label>
              <input id={c.clave} type="range" min={c.min} max={c.max} step={c.paso} value={v} disabled={soloLectura}
                onChange={(e) => setValores({ ...valores, [c.clave]: Number(e.target.value) })} style={{ accentColor: "var(--celeste)", width: "100%" }} />
            </div>
          );
        })}
        {error && <Aviso tipo="error">{error}</Aviso>}
        <div className="fila">
          {soloLectura && <Aviso>Tienes acceso de solo lectura: el dueño del negocio puede cambiar estos avisos.</Aviso>}
          <button className="btn primario" onClick={guardar} disabled={guardando || soloLectura}>
            {guardando ? <Loader2 size={16} className="girando" /> : <Save size={16} />} Guardar y recalcular
          </button>
          <button className="btn fantasma" onClick={() => setValores(empresa.umbrales)}>
            <RotateCcw size={16} /> Deshacer cambios
          </button>
        </div>
      </div>
    </Tarjeta>
  );
}

export function Alertas() {
  const { empresa } = useSesion();
  const { params, seleccion } = usePeriodo();
  const id = empresa?.id_empresa;
  // El mismo pedido alimenta el contador del menú lateral: al guardar umbrales,
  // recargar() actualiza las dos vistas sin recargar la página.
  const base = useAlertas();
  const [redactadas, setRedactadas] = useState<Alerta[] | null>(null);
  const [redactando, setRedactando] = useState(false);
  const [filtro, setFiltro] = useState<"todas" | NivelAlerta>("todas");

  // La versión redactada por IA se pide en segundo plano; mientras tanto se muestran las plantillas.
  useEffect(() => {
    setRedactadas(null);
    if (!base.datos?.length || !id) return;
    let vigente = true;
    setRedactando(true);
    api
      .get<Alerta[]>(`/empresas/${id}/alertas`, { ...params, redactar_ia: true })
      .then((r) => vigente && setRedactadas(r))
      .catch(() => undefined)
      .finally(() => vigente && setRedactando(false));
    return () => {
      vigente = false;
    };
  }, [base.datos, id, params]);

  const lista = (redactadas ?? base.datos ?? []).filter((a) => filtro === "todas" || a.nivel === filtro);
  const conteo = (n: NivelAlerta) => base.datos?.filter((a) => a.nivel === n).length ?? 0;

  return (
    <Pagina eyebrow="Alertas" titulo="Lo que necesita tu atención"
      descripcion={`Avisos de ${seleccion?.etiqueta.toLowerCase() ?? "este periodo"}. El sistema detecta cada alerta y calcula sus cifras; la IA local solo la redacta en palabras sencillas.`}
    >
      {base.error && <Aviso tipo="error">{base.error}</Aviso>}
      <div className="grid grid-lateral">
        <div className="pila" style={{ gap: 14 }}>
          <Segmentado etiqueta="Filtrar alertas" valor={filtro} onChange={setFiltro}
            opciones={[
              { valor: "todas", texto: `Todas (${base.datos?.length ?? 0})` },
              { valor: "rojo", texto: `🔴 Acción (${conteo("rojo")})` },
              { valor: "amarillo", texto: `🟡 Atención (${conteo("amarillo")})` },
              { valor: "verde", texto: `🟢 Bien (${conteo("verde")})` },
            ]} />
          {base.cargando && !base.datos && <TarjetaCargando alto={90} />}
          {base.datos && lista.length === 0 && (
            <EstadoVacio icono={Sparkles} titulo="Nada por aquí" texto="No hay alertas de este tipo en el periodo seleccionado." />
          )}
          <AnimatePresence mode="popLayout">
            {lista.map((a, i) => <TarjetaAlerta key={a.id} alerta={a} indice={i} redactando={redactando} />)}
          </AnimatePresence>
          <p className="mini muted justificado">
            Los consejos son orientativos y no constituyen asesoría financiera, contable ni fiscal. Las cifras de cada aviso las
            calcula el sistema con tus datos; la IA no hace cuentas.
          </p>
        </div>
        <PanelUmbrales alGuardar={base.recargar} />
      </div>
    </Pagina>
  );
}
