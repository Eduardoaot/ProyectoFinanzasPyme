import { motion } from "framer-motion";
import {
  Bell,
  Bot,
  ChartColumnBig,
  CreditCard,
  FileSpreadsheet,
  Landmark,
  LayoutDashboard,
  Package,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useSesion } from "../../context/Sesion";
import { Logo } from "../ui/basicos";

export const MODULOS: { ruta: string; texto: string; icono: LucideIcon; pregunta: string }[] = [
  { ruta: "/", texto: "Resumen", icono: LayoutDashboard, pregunta: "¿Cómo voy?" },
  { ruta: "/finanzas", texto: "Finanzas", icono: ChartColumnBig, pregunta: "¿Estoy ganando?" },
  { ruta: "/productos", texto: "Productos", icono: Package, pregunta: "¿Qué producto me deja más?" },
  { ruta: "/flujo", texto: "Flujo de efectivo", icono: Wallet, pregunta: "¿Me va a alcanzar?" },
  { ruta: "/alertas", texto: "Alertas", icono: Bell, pregunta: "¿Qué atiendo primero?" },
];

export const PLANEACION: { ruta: string; texto: string; icono: LucideIcon; pregunta: string }[] = [
  { ruta: "/proyecciones", texto: "Proyecciones y consejos", icono: TrendingUp, pregunta: "¿Cómo me va a ir? ¿Qué hago?" },
  { ruta: "/impuestos", texto: "Impuestos", icono: Landmark, pregunta: "¿Cuánto debo pagar al SAT?" },
  { ruta: "/deudas", texto: "Deudas", icono: CreditCard, pregunta: "¿Cuánto debo y cuándo termino?" },
];

export const HERRAMIENTAS = [
  { ruta: "/asistente", texto: "Asistente Clara", icono: Bot },
  { ruta: "/importar", texto: "Importar datos", icono: FileSpreadsheet },
];

export function Sidebar({ alertasRojas, alNavegar }: { alertasRojas: number; alNavegar?: () => void }) {
  const { usuario, empresa } = useSesion();
  const item = (ruta: string, texto: string, Icono: LucideIcon, contador?: number) => (
    <NavLink key={ruta} to={ruta} end={ruta === "/"} className={({ isActive }) => `nav-item ${isActive ? "activo" : ""}`} onClick={alNavegar}>
      {({ isActive }) => (
        <>
          {isActive && <motion.span layoutId="nav-activo" className="fondo" transition={{ type: "spring", stiffness: 420, damping: 36 }} />}
          <Icono size={18} aria-hidden="true" />
          <span>{texto}</span>
          {!!contador && (
            <motion.span className="contador" initial={{ scale: 0 }} animate={{ scale: 1 }} aria-label={`${contador} alertas en rojo`}>
              {contador}
            </motion.span>
          )}
        </>
      )}
    </NavLink>
  );

  return (
    <aside className="sidebar" aria-label="Menú principal">
      <div className="marca">
        <Logo tamano={38} />
      </div>
      <nav>
        <span className="seccion">Tu negocio</span>
        {MODULOS.map((m) => item(m.ruta, m.texto, m.icono, m.ruta === "/alertas" ? alertasRojas : undefined))}
        <span className="seccion">Planea y cumple</span>
        {PLANEACION.map((m) => item(m.ruta, m.texto, m.icono))}
        <span className="seccion">Herramientas</span>
        {HERRAMIENTAS.map((h) => item(h.ruta, h.texto, h.icono))}
      </nav>
      <div className="pie">
        <strong>{usuario?.nombre}</strong>
        <div>{empresa ? `${empresa.giro}${empresa.ciudad ? ` · ${empresa.ciudad}` : ""}` : " "}</div>
      </div>
    </aside>
  );
}
