// Formato de cifras en español de México. Solo formatea: los cálculos vienen del backend.

const mxn = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 2 });
const mxnCorto = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
const compacto = new Intl.NumberFormat("es-MX", { notation: "compact", maximumFractionDigits: 1 });
const entero = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 1 });

export function dinero(valor: number | null | undefined, decimales = true): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  return (decimales && !Number.isInteger(valor) ? mxn : mxnCorto).format(valor);
}

export function dineroCompacto(valor: number): string {
  return Math.abs(valor) >= 10000 ? `$${compacto.format(valor)}` : mxnCorto.format(valor);
}

export function pct(valor: number | null | undefined, decimales = 1): string {
  if (valor === null || valor === undefined) return "—";
  return `${(valor * 100).toFixed(decimales)}%`;
}

export function cambio(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "sin comparación";
  if (Math.abs(valor) >= 10) return valor > 0 ? "+más de 999%" : "−más de 999%";
  const signo = valor > 0 ? "+" : valor < 0 ? "−" : "";
  return `${signo}${Math.abs(valor * 100).toFixed(1)}%`;
}

export function numero(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return entero.format(valor);
}

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

export function fechaCorta(iso: string): string {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MESES[m - 1]} ${String(a).slice(2)}`;
}

export function fechaLarga(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("es-MX", { day: "numeric", month: "long", year: "numeric" });
}

/** "17 de octubre" (sin año): para fechas cercanas, que se leen mejor así. */
export function diaMes(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("es-MX", { day: "numeric", month: "long" });
}

/** "del 1 al 30 de septiembre" o "del 1 de septiembre al 3 de octubre". */
export function rangoDias(desde: string, hasta: string): string {
  const mismoMes = desde.slice(0, 7) === hasta.slice(0, 7);
  return mismoMes ? `del ${Number(desde.slice(8, 10))} al ${diaMes(hasta)}` : `del ${diaMes(desde)} al ${diaMes(hasta)}`;
}

/** Texto plano para la voz: quita Markdown, emojis y lee "$" como pesos. */
export function textoParaVoz(markdown: string): string {
  return markdown
    .replace(/^#+\s*/gm, "")
    .replace(/\*\*|__|_|`|>/g, "")
    .replace(/^\s*[-•]\s*/gm, "")
    .replace(/[🔴🟡🟢⚪]/gu, "")
    .replace(/\$\s?(-?[\d,]+(?:\.\d+)?)/g, (_, n: string) => `${n} pesos`)
    .replace(/(\d)\.(\d)%/g, "$1 punto $2 por ciento")
    .replace(/%/g, " por ciento")
    .replace(/\n{2,}/g, ". ")
    .replace(/\n/g, ". ")
    .replace(/\.\s*\./g, ".")
    .trim();
}
