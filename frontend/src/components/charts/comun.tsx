// Piezas compartidas por todas las gráficas: colores por rol, tooltip y leyenda.
// Los colores salen de tokens CSS validados para daltonismo (ver styles/tokens.css).

import { dinero } from "../../lib/formato";

export const SERIE = {
  ventas: "var(--s1)",
  gastos: "var(--s2)",
  utilidad: "var(--s3)",
  s4: "var(--s4)",
  s5: "var(--s5)",
  s6: "var(--s6)",
} as const;

/** Orden fijo de colores categóricos (nunca se recicla: más de 6 categorías se agrupan en "Otros"). */
export const CATEGORICOS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)"];

export const EJE = {
  stroke: "var(--axis)",
  fontSize: 12,
  tickLine: false,
  axisLine: false,
} as const;

export interface FilaTooltip {
  nombre: string;
  valor: number;
  color: string;
  formato?: (v: number) => string;
  linea?: boolean;
}

interface PropsTooltip {
  active?: boolean;
  label?: string | number;
  payload?: { name?: string; value?: number | number[]; color?: string; fill?: string; dataKey?: string | number; payload?: Record<string, unknown> }[];
  titulo?: (label: string | number | undefined, payload: Record<string, unknown> | undefined) => string;
  formato?: (v: number) => string;
  nombres?: Record<string, string>;
}

export function TooltipGrafica({ active, label, payload, titulo, formato = (v) => dinero(v), nombres = {} }: PropsTooltip) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip-grafica">
      <div className="t">{titulo ? titulo(label, payload[0]?.payload) : label}</div>
      {payload
        .filter((p) => p.value !== undefined && p.value !== null && !String(p.dataKey).startsWith("_") && !String(p.name ?? "").startsWith("_"))
        .map((p) => {
          // Las bandas (Area con [mínimo, máximo]) se muestran como rango "de $X a $Y".
          const rango = Array.isArray(p.value) ? p.value : null;
          if (rango && rango.some((v) => v === null || v === undefined || Number.isNaN(Number(v)))) return null;
          return (
            <div className="r" key={String(p.dataKey)}>
              <span className="m">
                <i className="p" style={{ background: rango ? (p.fill ?? p.color) : p.color, opacity: rango ? 0.45 : 1 }} />
                {nombres[String(p.dataKey)] ?? p.name}
              </span>
              <strong className="num">
                {rango ? `${formato(Math.min(...rango.map(Number)))} – ${formato(Math.max(...rango.map(Number)))}` : formato(Number(p.value))}
              </strong>
            </div>
          );
        })}
    </div>
  );
}

export function Leyenda({ items }: { items: { nombre: string; color: string; tipo?: "barra" | "linea" | "punteada" }[] }) {
  return (
    <div className="leyenda" aria-hidden="true">
      {items.map((i) => (
        <span key={i.nombre}>
          <i
            className={i.tipo === "linea" ? "linea" : i.tipo === "punteada" ? "punteada" : ""}
            style={{ background: i.tipo === "punteada" ? undefined : i.color, color: i.color }}
          />
          {i.nombre}
        </span>
      ))}
    </div>
  );
}
