import { CalendarRange, Menu, Moon, Sun } from "lucide-react";
import { usePeriodo } from "../../context/Periodo";
import { useSesion } from "../../context/Sesion";
import { MenuUsuario } from "./MenuUsuario";
import { SelectorEmpresa } from "./SelectorEmpresa";

export function Topbar({ tema, alternarTema, abrirMenu }: { tema: "light" | "dark"; alternarTema: () => void; abrirMenu: () => void }) {
  const { usuario, empresas, empresa, idEmpresa, cambiarEmpresa, salir } = useSesion();
  const { periodos, meses, setMeses, ventanas, seleccion, setClave } = usePeriodo();
  const actual = empresas.find((e) => e.id_empresa === idEmpresa);
  const nombre = actual?.nombre_negocio ?? empresa?.nombre_negocio ?? "—";

  return (
    <header className="topbar">
      <button className="btn icono fantasma menu-movil" onClick={abrirMenu} aria-label="Abrir menú">
        <Menu size={20} />
      </button>
      <SelectorEmpresa empresas={empresas} idActual={idEmpresa ?? undefined} nombre={nombre} onCambiar={cambiarEmpresa} />
      <div className="espacio" />
      {periodos.length > 0 && (
        <div className="filtro-periodo">
          <CalendarRange size={18} color="var(--muted)" aria-hidden="true" />
          <label className="sr-only" htmlFor="periodo-ancho">
            Periodo
          </label>
          <select id="periodo-ancho" className="select" value={meses} onChange={(e) => setMeses(e.target.value)}>
            {periodos.map((o) => (
              <option key={o.clave} value={o.clave}>
                {o.texto}
              </option>
            ))}
          </select>
          <label className="sr-only" htmlFor="periodo-ventana">
            Mes o rango
          </label>
          <select id="periodo-ventana" className="select" value={seleccion?.clave ?? ""} onChange={(e) => setClave(e.target.value)}>
            {ventanas.map((v) => (
              <option key={v.clave} value={v.clave}>
                {v.etiqueta}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="topbar-cuenta">
        <button className="btn icono fantasma" onClick={alternarTema} aria-label={tema === "dark" ? "Usar tema claro" : "Usar tema oscuro"}>
          {tema === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        <MenuUsuario usuario={usuario} onSalir={salir} />
      </div>
    </header>
  );
}
