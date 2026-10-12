import { AnimatePresence, motion } from "framer-motion";
import { ALargeSmall, Check } from "lucide-react";
import { useId, useState } from "react";
import { useMenuEmergente } from "../../hooks/useMenuEmergente";
import { aplicarTamanoTexto, leerTamanoTexto, TAMANOS, type TamanoTexto as Tamano } from "../../lib/tamanoTexto";

/** Botón "Aa" de la barra superior: cambia el tamaño de todo el texto de la app. */
export function TamanoTexto() {
  const { abierto, setAbierto, caja } = useMenuEmergente();
  const [actual, setActual] = useState<Tamano>(leerTamanoTexto);
  const idMenu = useId();

  const elegir = (t: Tamano) => {
    setActual(t);
    aplicarTamanoTexto(t);
  };

  return (
    <div className="menu-usuario" ref={caja}>
      <button type="button" className="btn icono fantasma" onClick={() => setAbierto((v) => !v)}
        aria-haspopup="true" aria-expanded={abierto} aria-controls={idMenu} aria-label="Tamaño del texto" title="Tamaño del texto">
        <ALargeSmall size={20} aria-hidden="true" />
      </button>
      <AnimatePresence>
        {abierto && (
          <motion.div id={idMenu} className="panel-usuario panel-tamano" role="group" aria-label="Tamaño del texto"
            initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.16 }}>
            <strong>Tamaño del texto</strong>
            {TAMANOS.map((t) => (
              <button key={t.clave} type="button" className={`opcion-tamano ${actual === t.clave ? "activa" : ""}`}
                aria-pressed={actual === t.clave} onClick={() => elegir(t.clave)}>
                <span className="muestra" style={{ fontSize: `${t.escala}em` }} aria-hidden="true">Aa</span>
                <span className="nombre">{t.texto}</span>
                {actual === t.clave && <Check size={16} aria-hidden="true" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
