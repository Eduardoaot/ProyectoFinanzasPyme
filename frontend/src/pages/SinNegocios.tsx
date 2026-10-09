import { motion } from "framer-motion";
import { Loader2, LogOut, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Aviso, Logo } from "../components/ui/basicos";
import { useSesion } from "../context/Sesion";

/** Cuenta sin negocios (p. ej. un contador recién registrado): explica cómo conseguir acceso. */
export function SinNegocios() {
  const { usuario, recargarEmpresas, salir } = useSesion();
  const [revisando, setRevisando] = useState(false);
  const [sinCambios, setSinCambios] = useState(false);

  const revisar = async () => {
    setRevisando(true);
    setSinCambios(false);
    try {
      await recargarEmpresas();
      setSinCambios(true);      // si ya tiene negocios, esta pantalla desaparece y el aviso no se ve
    } finally {
      setRevisando(false);
    }
  };

  return (
    <main className="sin-negocios">
      <motion.div className="card caja" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <Logo tamano={40} />
        <h1>Hola, {usuario?.nombre.split(" ")[0]}</h1>
        <p className="justificado">
          Todavía no tienes acceso a ningún negocio. Pídele al dueño que te invite con tu correo
          <strong> {usuario?.email}</strong>. Lo hace desde su panel, en <strong>Mi equipo</strong>.
        </p>
        <p className="muted pequeno justificado">
          Cuando te invite podrás ver sus reportes, gráficas y alertas, y preguntarle a Clara. Si te invitan varios negocios,
          podrás cambiar entre ellos desde la parte de arriba.
        </p>
        {sinCambios && <Aviso>Aún no tienes invitaciones. Vuelve a revisar cuando el dueño te avise.</Aviso>}
        <div className="fila envolver" style={{ gap: 8 }}>
          <button className="btn primario" onClick={revisar} disabled={revisando}>
            {revisando ? <Loader2 size={16} className="girando" /> : <RefreshCw size={16} />} Ya me invitaron, revisar
          </button>
          <button className="btn fantasma" onClick={salir}>
            <LogOut size={16} /> Cerrar sesión
          </button>
        </div>
      </motion.div>
    </main>
  );
}
