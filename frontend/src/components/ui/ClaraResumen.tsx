import { Sparkles } from "lucide-react";
import { useApi } from "../../hooks/useApi";
import type { ClaraTexto } from "../../lib/predictivo";
import { Esqueleto } from "./basicos";

/** Explicación de Clara de un apartado. Ella solo redacta: las cifras ya vienen calculadas del backend. */
export function ClaraResumen({ ruta, version }: { ruta: string | null; version?: string | number }) {
  const clara = useApi<ClaraTexto>(ruta, { v: version });
  return (
    <section className="card clara-resumen" aria-label="Explicación de Clara">
      <div className="fila" style={{ gap: 10 }}>
        <span className="avatar" aria-hidden="true"><Sparkles size={16} /></span>
        <strong>Clara te lo explica</strong>
        {clara.datos?.redactado_por_ia && <span className="chip celeste">Redactado por IA con cifras del sistema</span>}
      </div>
      {clara.cargando && !clara.datos ? (
        <div className="pila"><Esqueleto alto={14} /><Esqueleto alto={14} ancho="80%" /></div>
      ) : (
        <p className="justificado" style={{ margin: 0 }}>{clara.datos?.texto ?? clara.error ?? ""}</p>
      )}
      <p className="mini muted" style={{ margin: 0 }}>{clara.datos?.aviso ?? "Orientación general, no constituye asesoría financiera."}</p>
    </section>
  );
}
