import { LayoutDashboard, Moon, Sun } from "lucide-react";
import { Suspense } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { useSesion } from "../../context/Sesion";
import { guardarModo } from "../../lib/modo";
import { Logo } from "../ui/basicos";
import { MenuUsuario } from "./MenuUsuario";
import { SelectorEmpresa } from "./SelectorEmpresa";

/** Marco del Inicio sencillo: sin menú lateral, solo el negocio, la cuenta y el paso al modo avanzado. */
export function LayoutSencillo({ tema, alternarTema }: { tema: "light" | "dark"; alternarTema: () => void }) {
  const { usuario, empresas, empresa, idEmpresa, cambiarEmpresa, salir } = useSesion();
  const navegar = useNavigate();
  const nombre = empresas.find((e) => e.id_empresa === idEmpresa)?.nombre_negocio ?? empresa?.nombre_negocio ?? "—";

  const irAvanzado = () => {
    guardarModo(usuario?.id_usuario, "avanzado");
    navegar("/resumen");
  };

  return (
    <div className="app-sencilla">
      <header className="topbar topbar-sencilla">
        <span className="logo-sencillo"><Logo tamano={32} conTexto={false} /></span>
        <SelectorEmpresa empresas={empresas} idActual={idEmpresa ?? undefined} nombre={nombre} onCambiar={cambiarEmpresa} />
        <div className="topbar-cuenta">
          <button className="btn icono fantasma" onClick={alternarTema} aria-label={tema === "dark" ? "Usar tema claro" : "Usar tema oscuro"}>
            {tema === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <MenuUsuario usuario={usuario} onSalir={salir} />
        </div>
      </header>
      <main className="contenido-sencillo">
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
        <section className="pase-avanzado">
          <p>¿Quieres ver todo con más detalle, con todas las gráficas y tablas?</p>
          <button type="button" className="btn grande" onClick={irAvanzado}>
            <LayoutDashboard size={20} /> Ver todo con detalle (modo avanzado)
          </button>
        </section>
      </main>
    </div>
  );
}
