import { motion } from "framer-motion";
import {
  Bell,
  Bot,
  ChartColumnBig,
  CreditCard,
  FileSpreadsheet,
  House,
  Landmark,
  LayoutDashboard,
  Package,
  TrendingUp,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { useSesion } from "../../context/Sesion";
import { guardarModo } from "../../lib/modo";
import { Logo } from "../ui/basicos";

// Sin `export`: un archivo de componente que exporta constantes rompe el Fast Refresh de Vite.
const MODULOS: { ruta: string; texto: string; icono: LucideIcon; pregunta: string }[] = [
  { ruta: "/resumen", texto: "Resumen", icono: LayoutDashboard, pregunta: "Ventas, ganancia y margen" },
  { ruta: "/finanzas", texto: "Finanzas", icono: ChartColumnBig, pregunta: "Estado de resultados y gastos" },
  { ruta: "/productos", texto: "Productos", icono: Package, pregunta: "Ganancia e inventario" },
  { ruta: "/flujo", texto: "Flujo de efectivo", icono: Wallet, pregunta: "Entradas y salidas de caja" },
  { ruta: "/alertas", texto: "Alertas", icono: Bell, pregunta: "Avisos por urgencia" },
];

const PLANEACION: { ruta: string; texto: string; icono: LucideIcon; pregunta: string }[] = [
  { ruta: "/proyecciones", texto: "Proyecciones y consejos", icono: TrendingUp, pregunta: "Pronóstico, compras y ahorro" },
  { ruta: "/impuestos", texto: "Impuestos", icono: Landmark, pregunta: "ISR, IVA y deducciones" },
  { ruta: "/deudas", texto: "Deudas", icono: CreditCard, pregunta: "Saldos, pagos y plan" },
];

const HERRAMIENTAS = [
  { ruta: "/asistente", texto: "Asistente Clara", icono: Bot },
  { ruta: "/importar", texto: "Importar datos", icono: FileSpreadsheet },
  { ruta: "/equipo", texto: "Mi equipo", icono: Users },
];

export function Sidebar({ alertasRojas, alNavegar }: { alertasRojas: number; alNavegar?: () => void }) {
  const { usuario } = useSesion();
  const item = (ruta: string, texto: string, Icono: LucideIcon, contador?: number) => (
    <NavLink key={ruta} to={ruta} end className={({ isActive }) => `nav-item ${isActive ? "activo" : ""}`} onClick={alNavegar}>
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
      <Link to="/" className="volver-sencillo" onClick={() => { guardarModo(usuario?.id_usuario, "sencillo"); alNavegar?.(); }}>
        <House size={18} aria-hidden="true" /> Volver al Inicio sencillo
      </Link>
      <nav>
        <span className="seccion">Tu negocio</span>
        {MODULOS.map((m) => item(m.ruta, m.texto, m.icono, m.ruta === "/alertas" ? alertasRojas : undefined))}
        <span className="seccion">Planea y cumple</span>
        {PLANEACION.map((m) => item(m.ruta, m.texto, m.icono))}
        <span className="seccion">Herramientas</span>
        {HERRAMIENTAS.map((h) => item(h.ruta, h.texto, h.icono))}
      </nav>
    </aside>
  );
}
