import { useEffect, useRef, useState } from "react";

/** Estado de un menú desplegable que se cierra al hacer clic fuera de `caja` o con Escape. */
export function useMenuEmergente<T extends HTMLElement = HTMLDivElement>() {
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<T>(null);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: PointerEvent) => {
      if (!caja.current?.contains(e.target as Node)) setAbierto(false);
    };
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && setAbierto(false);
    document.addEventListener("pointerdown", fuera);
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("pointerdown", fuera);
      document.removeEventListener("keydown", tecla);
    };
  }, [abierto]);

  return { abierto, setAbierto, caja };
}
