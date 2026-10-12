// Tamaño del texto elegido por la persona. Casi todo el diseño usa rem, así que basta con escalar
// el tamaño de letra de <html>. Se guarda en este navegador (es una preferencia de lectura).

export type TamanoTexto = "chico" | "normal" | "grande" | "muy_grande";

export const TAMANOS: { clave: TamanoTexto; texto: string; escala: number }[] = [
  { clave: "chico", texto: "Chico", escala: 0.9 },
  { clave: "normal", texto: "Normal", escala: 1 },
  { clave: "grande", texto: "Grande", escala: 1.125 },
  { clave: "muy_grande", texto: "Muy grande", escala: 1.25 },
];

const CLAVE = "cc.tamano-texto";

export function leerTamanoTexto(): TamanoTexto {
  try {
    const guardado = localStorage.getItem(CLAVE);
    return TAMANOS.some((t) => t.clave === guardado) ? (guardado as TamanoTexto) : "normal";
  } catch {
    return "normal";
  }
}

export function aplicarTamanoTexto(tamano: TamanoTexto) {
  const escala = TAMANOS.find((t) => t.clave === tamano)?.escala ?? 1;
  document.documentElement.style.fontSize = escala === 1 ? "" : `${escala * 100}%`;
  try {
    localStorage.setItem(CLAVE, tamano);
  } catch {
    /* sin almacenamiento: dura mientras la pestaña esté abierta */
  }
}
