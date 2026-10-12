import { motion } from "framer-motion";
import { ArrowRight, Sparkles, X, type LucideIcon } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useChatOpcional } from "../../context/Chat";

/**
 * Ventana emergente para ver el detalle de algo sin salir de la página.
 * - "centro": tarjeta al centro (en celular sube desde abajo).
 * - "lado": cajón lateral, para detalles con gráficas.
 * Se monta en <body> para que ninguna tarjeta animada (con transform) la recorte o la mueva.
 */
export function Emergente({ titulo, subtitulo, icono: Icono, onCerrar, children, pie, variante = "centro", ancho = "medio" }: {
  titulo: string;
  subtitulo?: ReactNode;
  icono?: LucideIcon;
  onCerrar: () => void;
  children: ReactNode;
  pie?: ReactNode;
  variante?: "centro" | "lado";
  ancho?: "chico" | "medio";
}) {
  const idTitulo = useId();
  const cerrar = useRef<HTMLButtonElement>(null);
  const alCerrar = useRef(onCerrar);
  alCerrar.current = onCerrar;

  useEffect(() => {
    const previo = document.activeElement as HTMLElement | null;
    cerrar.current?.focus();
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && alCerrar.current();
    document.addEventListener("keydown", tecla);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tecla);
      document.body.style.overflow = overflow;
      previo?.focus?.();
    };
  }, []);

  const lado = variante === "lado";
  return createPortal(
    <motion.div className={`velo-emergente ${variante}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onCerrar}>
      <motion.section className={`emergente ${variante} ${ancho}`} role="dialog" aria-modal="true" aria-labelledby={idTitulo}
        initial={lado ? { x: "100%" } : { opacity: 0, y: 24, scale: 0.98 }}
        animate={lado ? { x: 0 } : { opacity: 1, y: 0, scale: 1 }}
        exit={lado ? { x: "100%" } : { opacity: 0, y: 24, scale: 0.98 }}
        transition={{ type: "spring", stiffness: 340, damping: 32 }} onClick={(e) => e.stopPropagation()}>
        <header className="emergente-cabecera">
          {Icono && <span className="emergente-icono" aria-hidden="true"><Icono size={18} /></span>}
          <div className="emergente-titulos">
            <h2 id={idTitulo}>{titulo}</h2>
            {subtitulo && <p>{subtitulo}</p>}
          </div>
          <button ref={cerrar} type="button" className="btn icono fantasma" onClick={onCerrar} aria-label="Cerrar">
            <X size={18} />
          </button>
        </header>
        <div className="emergente-cuerpo">{children}</div>
        {pie && <footer className="emergente-pie">{pie}</footer>}
      </motion.section>
    </motion.div>,
    document.body,
  );
}

/** Lista de "nombre → cifra" para los detalles. Las cifras llegan ya calculadas y formateadas. */
export function ListaCifras({ filas }: { filas: { nombre: ReactNode; valor: ReactNode; tono?: "bien" | "mal" | "fuerte" }[] }) {
  return (
    <dl className="lista-cifras">
      {filas.map((f, i) => (
        <div key={i} className={f.tono ?? ""}>
          <dt>{f.nombre}</dt>
          <dd className="num">{f.valor}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Botón "Preguntar a Clara" del modo avanzado: cierra el detalle, abre el chat flotante y le manda la pregunta.
 * Fuera del proveedor del chat (modo sencillo, pruebas) no se muestra.
 */
export function BotonClara({ pregunta, antes, texto = "Preguntar a Clara" }: { pregunta: string; antes?: () => void; texto?: string }) {
  const chat = useChatOpcional();
  if (!chat) return null;
  return (
    <button type="button" className="btn celeste" onClick={() => {
      antes?.();
      chat.abrirChat();
      chat.enviar(pregunta);
    }}>
      <Sparkles size={16} aria-hidden="true" /> {texto}
    </button>
  );
}

/** Enlace a la sección completa, con el mismo aspecto en todos los detalles. */
export function IrASeccion({ a, texto = "Ver sección completa" }: { a: string; texto?: string }) {
  return (
    <Link to={a} className="btn">
      {texto} <ArrowRight size={16} aria-hidden="true" />
    </Link>
  );
}
