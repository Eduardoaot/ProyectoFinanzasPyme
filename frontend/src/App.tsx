import { AnimatePresence, MotionConfig, motion } from "framer-motion";
import { lazy, useEffect, useState } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { LayoutSencillo } from "./components/layout/LayoutSencillo";
import { Logo } from "./components/ui/basicos";
import { Pagina } from "./components/ui/Pagina";
import { ProveedorAlertas } from "./context/Alertas";
import { ProveedorChat } from "./context/Chat";
import { ProveedorPeriodo } from "./context/Periodo";
import { ProveedorSesion, useSesion } from "./context/Sesion";
import { leerModo } from "./lib/modo";
import { Acceso } from "./pages/Acceso";
import { SinNegocios } from "./pages/SinNegocios";

// Cada módulo se descarga solo cuando el usuario lo abre (carga inicial más ligera).
const InicioSencillo = lazy(() => import("./pages/InicioSencillo").then((m) => ({ default: m.InicioSencillo })));
const Resumen = lazy(() => import("./pages/Resumen").then((m) => ({ default: m.Resumen })));
const Finanzas = lazy(() => import("./pages/Finanzas").then((m) => ({ default: m.Finanzas })));
const Productos = lazy(() => import("./pages/Productos").then((m) => ({ default: m.Productos })));
const Flujo = lazy(() => import("./pages/Flujo").then((m) => ({ default: m.Flujo })));
const Alertas = lazy(() => import("./pages/Alertas").then((m) => ({ default: m.Alertas })));
const Proyecciones = lazy(() => import("./pages/Proyecciones").then((m) => ({ default: m.Proyecciones })));
const Impuestos = lazy(() => import("./pages/Impuestos").then((m) => ({ default: m.Impuestos })));
const Deudas = lazy(() => import("./pages/Deudas").then((m) => ({ default: m.Deudas })));
const Importar = lazy(() => import("./pages/Importar").then((m) => ({ default: m.Importar })));
const Perfil = lazy(() => import("./pages/Perfil").then((m) => ({ default: m.Perfil })));
const Equipo = lazy(() => import("./pages/Equipo").then((m) => ({ default: m.Equipo })));
const Asistente = lazy(() => import("./pages/Asistente").then((m) => ({ default: m.Asistente })));

type Tema = "light" | "dark";

function temaInicial(): Tema {
  try {
    const guardado = localStorage.getItem("cc.tema");
    if (guardado === "light" || guardado === "dark") return guardado;
  } catch {
    /* sin almacenamiento */
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function Cargando() {
  return (
    <motion.div style={{ minHeight: "100dvh", display: "grid", placeItems: "center" }} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <motion.div animate={{ scale: [1, 1.06, 1] }} transition={{ duration: 1.4, repeat: Infinity }}>
        <Logo tamano={56} conTexto={false} />
      </motion.div>
    </motion.div>
  );
}

function NoEncontrada() {
  return (
    <Pagina titulo="No encontramos esta página">
      <Link to="/" className="btn primario" style={{ alignSelf: "flex-start" }}>Volver al inicio</Link>
    </Pagina>
  );
}

function Rutas() {
  const { usuario, empresas, cargando } = useSesion();
  const [tema, setTema] = useState<Tema>(temaInicial);
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const alternarTema = () => setTema((t) => (t === "dark" ? "light" : "dark"));

  // Al entrar, quien eligió el modo avanzado la última vez llega directo a él. Solo se revisa al
  // iniciar sesión: después, tocar "Inicio sencillo" sí lleva al Inicio sencillo.
  useEffect(() => {
    if (usuario && ubicacion.pathname === "/" && leerModo(usuario.id_usuario) === "avanzado") navegar("/resumen", { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usuario?.id_usuario]);

  useEffect(() => {
    document.documentElement.dataset.theme = tema;
    try {
      localStorage.setItem("cc.tema", tema);
    } catch {
      /* sin almacenamiento */
    }
  }, [tema]);

  if (cargando) return <Cargando />;
  return (
    <AnimatePresence mode="wait">
      {!usuario ? (
        <motion.div key="acceso" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <Acceso />
        </motion.div>
      ) : empresas.length === 0 ? (
        <motion.div key="sin-negocios" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <SinNegocios />
        </motion.div>
      ) : (
        <motion.div key="app" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <ProveedorPeriodo>
            <ProveedorAlertas>
              <ProveedorChat>
              <Routes>
                <Route element={<LayoutSencillo tema={tema} alternarTema={alternarTema} />}>
                  <Route index element={<InicioSencillo />} />
                </Route>
                <Route element={<AppLayout tema={tema} alternarTema={alternarTema} />}>
                  <Route path="resumen" element={<Resumen />} />
                  <Route path="finanzas" element={<Finanzas />} />
                  <Route path="productos" element={<Productos />} />
                  <Route path="flujo" element={<Flujo />} />
                  <Route path="alertas" element={<Alertas />} />
                  <Route path="proyecciones" element={<Proyecciones />} />
                  <Route path="impuestos" element={<Impuestos />} />
                  <Route path="deudas" element={<Deudas />} />
                  <Route path="importar" element={<Importar />} />
                  <Route path="asistente" element={<Asistente />} />
                  <Route path="equipo" element={<Equipo />} />
                  <Route path="perfil" element={<Perfil />} />
                  <Route path="*" element={<NoEncontrada />} />
                </Route>
              </Routes>
              </ProveedorChat>
            </ProveedorAlertas>
          </ProveedorPeriodo>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <ProveedorSesion>
          <Rutas />
        </ProveedorSesion>
      </BrowserRouter>
    </MotionConfig>
  );
}
