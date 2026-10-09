import { AnimatePresence, motion } from "framer-motion";
import { MessageCircle, Sparkles, X } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useAlertas } from "../../context/Alertas";
import { useChat } from "../../context/Chat";
import { useSesion } from "../../context/Sesion";
import { Conversacion } from "../chat/Conversacion";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppLayout({ tema, alternarTema }: { tema: "light" | "dark"; alternarTema: () => void }) {
  const { empresa } = useSesion();
  const { chatAbierto, cerrarChat, alternarChat } = useChat();
  const { datos: alertas } = useAlertas();
  const ubicacion = useLocation();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [esMovil, setEsMovil] = useState(() => window.matchMedia("(max-width: 900px)").matches);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 900px)");
    const cambio = () => setEsMovil(mq.matches);
    mq.addEventListener("change", cambio);
    return () => mq.removeEventListener("change", cambio);
  }, []);
  useEffect(() => {
    setMenuAbierto(false);
    cerrarChat();
  }, [ubicacion.pathname, cerrarChat]);

  const rojas = alertas?.filter((a) => a.nivel === "rojo").length ?? 0;
  const enAsistente = ubicacion.pathname === "/asistente";

  return (
    <div className="app">
      {esMovil ? (
        <AnimatePresence>
          {menuAbierto && (
            <>
              <motion.div className="velo" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMenuAbierto(false)} />
              <motion.div style={{ position: "fixed", zIndex: 55, inset: 0, width: 0 }} initial={{ x: -320 }} animate={{ x: 0 }} exit={{ x: -320 }}
                transition={{ type: "spring", stiffness: 340, damping: 34 }}>
                <Sidebar alertasRojas={rojas} alNavegar={() => setMenuAbierto(false)} />
              </motion.div>
            </>
          )}
        </AnimatePresence>
      ) : (
        <Sidebar alertasRojas={rojas} />
      )}
      <div className="contenido">
        <Topbar tema={tema} alternarTema={alternarTema} abrirMenu={() => setMenuAbierto(true)} />
        <AnimatePresence mode="wait">
          <motion.div key={`${ubicacion.pathname}-${empresa?.id_empresa}`} style={{ display: "contents" }}>
            <Suspense fallback={null}>
              <Outlet />
            </Suspense>
          </motion.div>
        </AnimatePresence>
      </div>

      {!enAsistente && (
        <>
          <AnimatePresence>
            {chatAbierto && (
              <motion.div className="panel-chat" role="dialog" aria-label="Chat con Clara"
                initial={{ opacity: 0, scale: 0.9, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.92, y: 16 }}
                transition={{ type: "spring", stiffness: 320, damping: 30 }}>
                <Conversacion compacto />
              </motion.div>
            )}
          </AnimatePresence>
          <motion.button className="fab-chat" onClick={alternarChat} whileHover={{ y: -3 }} whileTap={{ scale: 0.95 }}
            initial={{ y: 80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.6, type: "spring", stiffness: 260, damping: 22 }}
            aria-expanded={chatAbierto} aria-label={chatAbierto ? "Cerrar chat" : "Abrir chat con Clara"}>
            <span className="orbe">{chatAbierto ? <X size={16} /> : <Sparkles size={16} />}</span>
            <span className="texto">{chatAbierto ? "Cerrar" : "Pregúntale a Clara"}</span>
            {!chatAbierto && <MessageCircle size={16} style={{ opacity: 0.5 }} className="texto" />}
          </motion.button>
        </>
      )}
    </div>
  );
}
