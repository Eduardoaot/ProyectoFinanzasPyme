import { createContext, useContext, type ReactNode } from "react";
import { useApi } from "../hooks/useApi";
import type { Alerta } from "../lib/tipos";
import { usePeriodo } from "./Periodo";
import { useSesion } from "./Sesion";

interface ValorAlertas {
  datos: Alerta[] | null;
  error: string | null;
  cargando: boolean;
  recargar: () => void;
}

const Contexto = createContext<ValorAlertas | null>(null);

/**
 * Un solo pedido de alertas para toda la app: el menú lateral cuenta las rojas
 * y la página de Alertas las muestra. Al guardar umbrales, `recargar()`
 * actualiza ambos lugares sin recargar la página.
 */
export function ProveedorAlertas({ children }: { children: ReactNode }) {
  const { empresa } = useSesion();
  const { params } = usePeriodo();
  const ruta = empresa?.tiene_datos && params.desde ? `/empresas/${empresa.id_empresa}/alertas` : null;
  const a = useApi<Alerta[]>(ruta, params);
  const valor = { datos: a.datos, error: a.error, cargando: a.cargando, recargar: a.recargar };
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useAlertas(): ValorAlertas {
  const v = useContext(Contexto);
  if (!v) throw new Error("useAlertas fuera de ProveedorAlertas");
  return v;
}
