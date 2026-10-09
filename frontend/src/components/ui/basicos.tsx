import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, CheckCircle2, CircleHelp, Info, Minus, OctagonAlert, type LucideIcon } from "lucide-react";
import { useEffect, useId, type ReactNode } from "react";
import { cambio } from "../../lib/formato";
import type { Semaforo as TipoSemaforo } from "../../lib/tipos";

/* ---------- Logo ---------- */
export function Logo({ tamano = 36, conTexto = true, claro = false }: { tamano?: number; conTexto?: boolean; claro?: boolean }) {
  return (
    <span className="fila" style={{ gap: 10 }}>
      <svg width={tamano} height={tamano} viewBox="0 0 64 64" aria-hidden="true">
        <rect width="64" height="64" rx="16" fill={claro ? "#ffffff" : "#0d1117"} />
        {[
          { x: 14, y: 34, h: 16, o: 0.55 },
          { x: 28, y: 25, h: 25, o: 0.8 },
          { x: 42, y: 16, h: 34, o: 1 },
        ].map((b, i) => (
          <motion.rect
            key={b.x}
            x={b.x}
            width="8"
            rx="3"
            fill="#4a90d9"
            opacity={b.o}
            initial={{ y: 50, height: 0 }}
            animate={{ y: b.y, height: b.h }}
            transition={{ delay: 0.15 + i * 0.12, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          />
        ))}
        <motion.path
          d="M13 27 L26 18 L36 22 L51 10"
          fill="none"
          stroke={claro ? "#0d1117" : "#ffffff"}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ delay: 0.5, duration: 0.8, ease: "easeInOut" }}
        />
      </svg>
      {conTexto && (
        <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
          <strong style={{ fontSize: tamano * 0.46, letterSpacing: "-0.02em" }}>Cuentas Claras</strong>
          <span style={{ fontSize: Math.max(11, tamano * 0.3), opacity: 0.6 }}>Finanzas para tu negocio</span>
        </span>
      )}
    </span>
  );
}

/* ---------- Número animado (cuenta hacia arriba) ---------- */
export function NumeroAnimado({ valor, formato, className }: { valor: number; formato: (n: number) => string; className?: string }) {
  const mv = useMotionValue(0);
  const texto = useTransform(mv, (v) => formato(v));
  useEffect(() => {
    const control = animate(mv, valor, { duration: 1.1, ease: [0.22, 1, 0.36, 1] });
    return () => control.stop();
  }, [valor, mv]);
  return (
    <motion.span className={`num ${className ?? ""}`} aria-label={formato(valor)}>
      {texto}
    </motion.span>
  );
}

/* ---------- Ayuda (término técnico en tooltip) ---------- */
export function Ayuda({ texto }: { texto: string }) {
  const id = useId();
  return (
    <span className="ayuda" tabIndex={0} aria-describedby={id}>
      <CircleHelp size={14} aria-hidden="true" />
      <span className="burbuja" role="tooltip" id={id}>
        {texto}
      </span>
    </span>
  );
}

/* ---------- Chip de cambio vs periodo anterior ---------- */
export function Cambio({ valor, invertido = false }: { valor: number | null; invertido?: boolean }) {
  if (valor === null || valor === undefined) return <span className="cambio neutro">Sin comparación</span>;
  const bueno = invertido ? valor < 0 : valor > 0;
  const clase = Math.abs(valor) < 0.0005 ? "neutro" : bueno ? "sube" : "baja";
  const Icono = valor > 0 ? ArrowUpRight : valor < 0 ? ArrowDownRight : Minus;
  return (
    <span className={`cambio ${clase} num`}>
      <Icono size={13} aria-hidden="true" />
      {cambio(valor)}
    </span>
  );
}

/* ---------- Semáforo (nunca solo color: ícono + texto) ---------- */
const SEMAFORO: Record<TipoSemaforo, { texto: string; Icono: LucideIcon }> = {
  verde: { texto: "Bien", Icono: CheckCircle2 },
  amarillo: { texto: "Atención", Icono: AlertTriangle },
  rojo: { texto: "Acción", Icono: OctagonAlert },
  sin_movimiento: { texto: "Sin ventas", Icono: Minus },
};

export function Semaforo({ estado, texto }: { estado: TipoSemaforo; texto?: string }) {
  const { texto: base, Icono } = SEMAFORO[estado];
  return (
    <span className={`semaforo ${estado}`}>
      <Icono size={13} aria-hidden="true" />
      {texto ?? base}
    </span>
  );
}

/* ---------- Esqueleto ---------- */
export function Esqueleto({ alto = 16, ancho = "100%", radio }: { alto?: number; ancho?: number | string; radio?: number }) {
  return <div className="esqueleto" style={{ height: alto, width: ancho, borderRadius: radio }} aria-hidden="true" />;
}

export function TarjetaCargando({ alto = 260 }: { alto?: number }) {
  return (
    <div className="card" aria-busy="true" aria-label="Cargando">
      <Esqueleto alto={18} ancho="40%" />
      <Esqueleto alto={alto} />
    </div>
  );
}

/* ---------- Avisos ---------- */
export function Aviso({ children, tipo = "info" }: { children: ReactNode; tipo?: "info" | "error" }) {
  return (
    <div className={`aviso ${tipo === "error" ? "error" : ""}`} role={tipo === "error" ? "alert" : "note"}>
      {tipo === "error" ? <OctagonAlert size={16} /> : <Info size={16} />}
      <div className="justificado">{children}</div>
    </div>
  );
}

/* ---------- Estado vacío ---------- */
export function EstadoVacio({ icono: Icono, titulo, texto, accion }: { icono: LucideIcon; titulo: string; texto: string; accion?: ReactNode }) {
  return (
    <motion.div className="card vacio" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <motion.div
        className="icono-grande"
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      >
        <Icono size={32} />
      </motion.div>
      <h2>{titulo}</h2>
      <p>{texto}</p>
      {accion}
    </motion.div>
  );
}

/* ---------- Control segmentado con pastilla animada ---------- */
export function Segmentado<T extends string>({
  opciones,
  valor,
  onChange,
  etiqueta,
}: {
  opciones: { valor: T; texto: string }[];
  valor: T;
  onChange: (v: T) => void;
  etiqueta: string;
}) {
  const id = useId();
  return (
    <div className="segmentado" role="group" aria-label={etiqueta}>
      {opciones.map((o) => (
        <button key={o.valor} type="button" aria-pressed={o.valor === valor} onClick={() => onChange(o.valor)}>
          {o.valor === valor && (
            <motion.span layoutId={`pastilla-${id}`} className="pastilla" transition={{ type: "spring", stiffness: 500, damping: 38 }} />
          )}
          {o.texto}
        </button>
      ))}
    </div>
  );
}

/* ---------- Tarjeta con entrada animada ---------- */
export function Tarjeta({
  children,
  className = "",
  retraso = 0,
  interactiva = true,
}: {
  children: ReactNode;
  className?: string;
  retraso?: number;
  interactiva?: boolean;
}) {
  return (
    <motion.section
      className={`card ${interactiva ? "interactiva" : ""} ${className}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: retraso, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.section>
  );
}

export function TituloTarjeta({ titulo, sub, icono: Icono, derecha }: { titulo: string; sub?: string; icono?: LucideIcon; derecha?: ReactNode }) {
  return (
    <div className="card-titulo">
      <div>
        <h3>
          {Icono && <Icono size={18} color="var(--celeste)" aria-hidden="true" />}
          {titulo}
        </h3>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {derecha}
    </div>
  );
}
