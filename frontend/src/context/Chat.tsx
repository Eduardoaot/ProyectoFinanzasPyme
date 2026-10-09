import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useConversacion, type Mensaje } from "../hooks/useConversacion";

export type { Mensaje } from "../hooks/useConversacion";

interface ValorChat {
  mensajes: Mensaje[];
  ocupado: boolean;
  chatAbierto: boolean;
  abrirChat: () => void;
  cerrarChat: () => void;
  alternarChat: () => void;
  enviar: (texto: string) => void;
  cancelar: () => void;
  limpiar: () => void;
  vozAutomatica: boolean;
  setVozAutomatica: (v: boolean) => void;
  hablando: string | null;
  leer: (m: Mensaje) => void;
  callar: () => void;
}

const Contexto = createContext<ValorChat | null>(null);

/** La conversación del chat flotante y de la página del Asistente (la misma en ambos lugares). */
export function ProveedorChat({ children }: { children: ReactNode }) {
  const conv = useConversacion();
  const [chatAbierto, setChatAbierto] = useState(false);
  const abrirChat = useCallback(() => setChatAbierto(true), []);
  const cerrarChat = useCallback(() => setChatAbierto(false), []);
  const alternarChat = useCallback(() => setChatAbierto((abierto) => !abierto), []);
  const { mensajes, ocupado, enviar, cancelar, limpiar, vozAutomatica, setVozAutomatica, hablando, leer, callar } = conv;

  const valor = useMemo<ValorChat>(
    () => ({
      mensajes, ocupado, chatAbierto, abrirChat, cerrarChat, alternarChat, enviar, cancelar, limpiar,
      vozAutomatica, setVozAutomatica, hablando, leer, callar,
    }),
    [mensajes, ocupado, chatAbierto, abrirChat, cerrarChat, alternarChat, enviar, cancelar, limpiar,
      vozAutomatica, setVozAutomatica, hablando, leer, callar],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useChat() {
  const v = useContext(Contexto);
  if (!v) throw new Error("useChat fuera de ProveedorChat");
  return v;
}
