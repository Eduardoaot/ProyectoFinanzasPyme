import { useCallback, useEffect, useRef } from "react";

const MARGEN_PX = 80;

/**
 * Desplazamiento de una conversación: baja sola mientras Clara escribe, pero solo si la persona ya estaba
 * hasta abajo. Si subió para releer algo, la deja ahí. Un mensaje nuevo (una pregunta) siempre baja.
 */
export function useSeguirAbajo(mensajes: readonly unknown[]) {
  const caja = useRef<HTMLDivElement>(null);
  const pegado = useRef(true);
  const cantidad = useRef(mensajes.length);

  const alDesplazar = useCallback(() => {
    const el = caja.current;
    if (el) pegado.current = el.scrollHeight - el.scrollTop - el.clientHeight < MARGEN_PX;
  }, []);

  useEffect(() => {
    const el = caja.current;
    const nuevo = mensajes.length > cantidad.current;
    cantidad.current = mensajes.length;
    if (!el || !(nuevo || pegado.current)) return;
    el.scrollTo?.({ top: el.scrollHeight });
    pegado.current = true;
  }, [mensajes]);

  return { caja, alDesplazar };
}
