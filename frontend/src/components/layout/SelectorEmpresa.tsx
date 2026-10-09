import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronDown, Eye, Store } from "lucide-react";
import { useId } from "react";
import { useMenuEmergente } from "../../hooks/useMenuEmergente";
import type { EmpresaResumen } from "../../lib/tipos";
import { Ayuda } from "../ui/basicos";

const TEXTO_CONSULTA =
  "El dueño te dio acceso de consulta (por ejemplo, como su contador). Puedes ver reportes, gráficas y alertas, " +
  "y preguntarle a Clara. No puedes subir archivos, borrar importaciones ni cambiar alertas, impuestos o deudas: " +
  "eso solo lo hace el dueño.";

const textoRol = (rol: EmpresaResumen["rol"]) => (rol === "dueno" ? "Eres dueño" : "Solo puedes ver");

/** Nombre del negocio actual; si la cuenta tiene varios, se vuelve un menú para cambiar entre ellos. */
export function SelectorEmpresa({
  empresas,
  idActual,
  nombre,
  onCambiar,
}: {
  empresas: EmpresaResumen[];
  idActual: number | undefined;
  nombre: string;
  onCambiar: (id: number) => void;
}) {
  const { abierto, setAbierto, caja } = useMenuEmergente();
  const idLista = useId();
  const actual = empresas.find((e) => e.id_empresa === idActual);
  const varias = empresas.length > 1;

  const elegir = (id: number) => {
    setAbierto(false);
    if (id !== idActual) onCambiar(id);
  };

  const consulta = actual?.rol === "consulta" && (
    <span className="chip acceso-consulta">
      <Eye size={13} aria-hidden="true" /> Solo puedes ver
      <Ayuda abajo texto={TEXTO_CONSULTA} />
    </span>
  );

  if (!varias) {
    return (
      <div className="selector-empresa">
        <span className="nombre-empresa">{nombre}</span>
        {consulta}
      </div>
    );
  }

  return (
    <div className="selector-empresa con-menu" ref={caja}>
      <button type="button" className="boton-empresa" onClick={() => setAbierto((v) => !v)}
        aria-haspopup="true" aria-expanded={abierto} aria-controls={idLista}
        title={`Cambiar de negocio (tienes ${empresas.length})`}>
        <span className="nombre-empresa">{nombre}</span>
        <span className="sr-only">. Cambiar de negocio, tienes {empresas.length}</span>
        <ChevronDown size={16} aria-hidden="true" className={abierto ? "girada" : ""} />
      </button>
      {consulta}
      <AnimatePresence>
        {abierto && (
          <motion.ul id={idLista} className="menu-empresas" aria-label="Tus negocios"
            initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.16 }}>
            {empresas.map((e) => {
              const elegida = e.id_empresa === idActual;
              return (
                <li key={e.id_empresa}>
                  <button type="button" className={`opcion-empresa ${elegida ? "elegida" : ""}`}
                    aria-current={elegida ? "true" : undefined} onClick={() => elegir(e.id_empresa)}>
                    <Store size={16} aria-hidden="true" className="icono-tienda" />
                    <span className="datos">
                      <strong>{e.nombre_negocio}</strong>
                      <span className="muted">
                        {e.giro}{e.ciudad ? ` · ${e.ciudad}` : ""} · {textoRol(e.rol)}
                      </span>
                    </span>
                    {elegida && <Check size={16} aria-hidden="true" className="palomita" />}
                  </button>
                </li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
