// Filtro global: un ancho (1 mes … 2 años) y una ventana con mes/año dentro del
// historial de la empresa (p. ej. "Julio – Septiembre 2026").

export interface OpcionPeriodo {
  clave: string;
  /** Texto corto para el control: "3 meses". */
  texto: string;
  /** Frase completa para los textos de la interfaz: "últimos 3 meses" (último periodo). */
  etiqueta: string;
  desde: string;
  hasta: string;
}

export interface VentanaPeriodo {
  clave: string;
  /** "Septiembre 2026" o "Julio – Septiembre 2026". */
  etiqueta: string;
  desde: string;
  hasta: string;
}

/** Anchuras del filtro, en meses. */
export const RANGOS_MESES = [1, 2, 3, 6, 12, 24];

const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
  "Noviembre", "Diciembre"];

const iso = (a: number, m: number, d: number) => `${a}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
const finDeMes = (a: number, m: number) => new Date(a, m, 0).getDate();

export function textoRango(meses: number): string {
  if (meses >= 12) return meses === 12 ? "1 año" : `${meses / 12} años`;
  return meses === 1 ? "1 mes" : `${meses} meses`;
}

const etiquetaRango = (meses: number) => {
  if (meses === 1) return "último mes";
  if (meses === 12) return "último año";
  return `últimos ${textoRango(meses)}`;
};

/** Últimos `meses` meses de calendario que terminan en el mes de la fecha de corte.
 * Alinear a meses completos hace que la comparación con el periodo anterior sea limpia:
 * jul–sep contra abr–jun. */
export function rangoAtras(corte: string, meses: number): { desde: string; hasta: string } {
  const [a, m] = corte.split("-").map(Number);
  const inicio = new Date(a, m - meses, 1);
  return { desde: iso(inicio.getFullYear(), inicio.getMonth() + 1, 1), hasta: corte };
}

/** Las opciones del primer select (las 6 anchuras), todas terminando en el último día con datos. */
export function rangosPeriodo(ultimo: string): OpcionPeriodo[] {
  return RANGOS_MESES.map((meses) => {
    const { desde, hasta } = rangoAtras(ultimo, meses);
    return { clave: String(meses), texto: textoRango(meses), etiqueta: etiquetaRango(meses), desde, hasta };
  });
}

/** Ventanas del segundo select: los últimos rangos posibles dentro del historial,
 * del más reciente al más antiguo (p. ej. 3 meses → "Julio – Septiembre 2026", …).
 * Siempre hay al menos una ventana; las que empezarían antes del historial se
 * recortan a la fecha del primer dato. */
export function ventanasPeriodo(primer: string, ultimo: string, meses: number): VentanaPeriodo[] {
  const [pa, pm] = primer.split("-").map(Number);
  const [ua, um] = ultimo.split("-").map(Number);
  const inicioPrimer = iso(pa, pm, 1);
  const ventanas: VentanaPeriodo[] = [];
  let primerAncla = true;
  for (let a = ua, m = um; ;) {
    const hasta = iso(a, m, finDeMes(a, m));
    let desde = rangoAtras(hasta, meses).desde;
    if (!primerAncla && desde < inicioPrimer) break;
    if (desde < inicioPrimer) desde = inicioPrimer;
    ventanas.push({ clave: `${a}-${m}`, etiqueta: etiquetaVentana(desde, hasta), desde, hasta });
    primerAncla = false;
    if (m === pm && a === pa) break;
    if (m === 1) {
      a -= 1;
      m = 12;
    } else {
      m -= 1;
    }
  }
  return ventanas;
}

function etiquetaVentana(desde: string, hasta: string): string {
  const [da, dm] = desde.split("-").map(Number);
  const [ha, hm] = hasta.split("-").map(Number);
  if (da === ha && dm === hm) return `${MESES[hm - 1]} ${ha}`;
  if (da === ha) return `${MESES[dm - 1]} – ${MESES[hm - 1]} ${ha}`;
  return `${MESES[dm - 1]} ${da} – ${MESES[hm - 1]} ${ha}`;
}

/** Últimos 12 meses completos que terminan en el mes de `hasta` (para gráficas mensuales). */
export function ultimosMeses(hasta: string, n: number, primer: string): { desde: string; hasta: string } {
  const [a, m] = hasta.split("-").map(Number);
  const inicio = new Date(a, m - n, 1);
  const desde = iso(inicio.getFullYear(), inicio.getMonth() + 1, 1);
  return { desde: desde < primer ? primer.slice(0, 8) + "01" : desde, hasta };
}

/** "2026-09" → "septiembre 2026" (para preguntarle a Clara por un mes concreto). */
export function mesLargo(periodo: string): string {
  const [a, m] = periodo.split("-").map(Number);
  return m >= 1 && m <= 12 ? `${MESES[m - 1].toLowerCase()} ${a}` : periodo;
}
