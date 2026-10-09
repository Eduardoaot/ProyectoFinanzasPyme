import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, LogOut, UserRound } from "lucide-react";
import { useId } from "react";
import { Link } from "react-router-dom";
import { useMenuEmergente } from "../../hooks/useMenuEmergente";
import type { Usuario } from "../../lib/tipos";

/** Botón de la cuenta (arriba a la derecha): muestra nombre y correo, y lleva al perfil o cierra sesión. */
export function MenuUsuario({ usuario, onSalir }: { usuario: Usuario | null; onSalir: () => void }) {
  const { abierto, setAbierto, caja } = useMenuEmergente();
  const idMenu = useId();
  if (!usuario) return null;
  const primerNombre = usuario.nombre.split(" ")[0];

  return (
    <div className="menu-usuario" ref={caja}>
      <button type="button" className="boton-usuario" onClick={() => setAbierto((v) => !v)}
        aria-haspopup="true" aria-expanded={abierto} aria-controls={idMenu} aria-label={`Tu cuenta: ${usuario.nombre}`}>
        <UserRound size={18} aria-hidden="true" />
        <span className="nombre-usuario">{primerNombre}</span>
        <ChevronDown size={14} aria-hidden="true" className={abierto ? "girada" : ""} />
      </button>
      <AnimatePresence>
        {abierto && (
          <motion.div id={idMenu} className="panel-usuario"
            initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.16 }}>
            <div className="datos-usuario">
              <strong>{usuario.nombre}</strong>
              <span className="muted pequeno">{usuario.email}</span>
            </div>
            <div className="acciones-usuario">
              <Link to="/perfil" className="btn" onClick={() => setAbierto(false)}>
                <UserRound size={16} /> Mi perfil
              </Link>
              <button type="button" className="btn fantasma" onClick={onSalir}>
                <LogOut size={16} /> Cerrar sesión
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
