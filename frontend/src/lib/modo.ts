// Modo de la app por usuario: "sencillo" (Inicio sencillo) o "avanzado" (panel con menú lateral).
// Solo se guarda cuando la persona lo elige con un botón; entrar a "Ver detalles" no cambia su modo.

export type Modo = "sencillo" | "avanzado";

const clave = (idUsuario: number) => `cc.modo.${idUsuario}`;

export function leerModo(idUsuario: number | undefined): Modo {
  if (idUsuario === undefined) return "sencillo";
  try {
    return localStorage.getItem(clave(idUsuario)) === "avanzado" ? "avanzado" : "sencillo";
  } catch {
    return "sencillo";
  }
}

export function guardarModo(idUsuario: number | undefined, modo: Modo) {
  if (idUsuario === undefined) return;
  try {
    localStorage.setItem(clave(idUsuario), modo);
  } catch {
    /* sin almacenamiento: se usa el Inicio sencillo */
  }
}
