// Cliente HTTP de la API. Toda petición lleva el token; el backend resuelve la empresa y el permiso.

const BASE = import.meta.env.VITE_API_URL ?? "/api";
const CLAVE_TOKEN = "cc.token";

export class ErrorApi extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export function guardarToken(token: string | null) {
  try {
    if (token) localStorage.setItem(CLAVE_TOKEN, token);
    else localStorage.removeItem(CLAVE_TOKEN);
  } catch {
    /* almacenamiento bloqueado: la sesión dura lo que la pestaña */
  }
}

export function leerToken(): string | null {
  try {
    return localStorage.getItem(CLAVE_TOKEN);
  } catch {
    return null;
  }
}

let alExpirar: (() => void) | null = null;
export function onSesionExpirada(fn: () => void) {
  alExpirar = fn;
}

function cabeceras(extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  const token = leerToken();
  if (token) h.set("Authorization", `Bearer ${token}`);
  return h;
}

async function manejar<T>(r: Response): Promise<T> {
  if (r.ok) {
    const tipo = r.headers.get("content-type") ?? "";
    return (tipo.includes("application/json") ? r.json() : r.blob()) as Promise<T>;
  }
  let mensaje = "Algo salió mal. Intenta de nuevo.";
  try {
    const cuerpo = await r.json();
    if (typeof cuerpo.detail === "string") mensaje = cuerpo.detail;
  } catch {
    /* respuesta sin JSON */
  }
  if (r.status === 401) alExpirar?.();
  if (r.status === 502 || r.status === 504) mensaje = "No pudimos conectar con el servidor. ¿Está corriendo el backend?";
  throw new ErrorApi(mensaje, r.status);
}

type Params = Record<string, string | number | boolean | null | undefined>;

function url(ruta: string, params?: Params): string {
  const qs = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  });
  const s = qs.toString();
  return `${BASE}${ruta}${s ? `?${s}` : ""}`;
}

export const api = {
  get<T>(ruta: string, params?: Params, signal?: AbortSignal): Promise<T> {
    return fetch(url(ruta, params), { headers: cabeceras(), signal }).then((r) => manejar<T>(r));
  },
  post<T>(ruta: string, cuerpo?: unknown): Promise<T> {
    return fetch(url(ruta), {
      method: "POST",
      headers: cabeceras({ "Content-Type": "application/json" }),
      body: JSON.stringify(cuerpo ?? {}),
    }).then((r) => manejar<T>(r));
  },
  put<T>(ruta: string, cuerpo: unknown): Promise<T> {
    return fetch(url(ruta), {
      method: "PUT",
      headers: cabeceras({ "Content-Type": "application/json" }),
      body: JSON.stringify(cuerpo),
    }).then((r) => manejar<T>(r));
  },
  patch<T>(ruta: string, cuerpo: unknown): Promise<T> {
    return fetch(url(ruta), {
      method: "PATCH",
      headers: cabeceras({ "Content-Type": "application/json" }),
      body: JSON.stringify(cuerpo),
    }).then((r) => manejar<T>(r));
  },
  delete<T>(ruta: string): Promise<T> {
    return fetch(url(ruta), { method: "DELETE", headers: cabeceras() }).then((r) => manejar<T>(r));
  },
  subir<T>(ruta: string, datos: FormData): Promise<T> {
    return fetch(url(ruta), { method: "POST", headers: cabeceras(), body: datos }).then((r) => manejar<T>(r));
  },
  /** Lee una respuesta NDJSON (streaming del chat) evento por evento. */
  async stream(ruta: string, cuerpo: unknown, alEvento: (e: Record<string, unknown>) => void, signal?: AbortSignal) {
    const r = await fetch(url(ruta), {
      method: "POST",
      headers: cabeceras({ "Content-Type": "application/json" }),
      body: JSON.stringify(cuerpo),
      signal,
    });
    if (!r.ok || !r.body) return manejar(r);
    const lector = r.body.getReader();
    const decodificador = new TextDecoder();
    let pendiente = "";
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      pendiente += decodificador.decode(value, { stream: true });
      const lineas = pendiente.split("\n");
      pendiente = lineas.pop() ?? "";
      for (const linea of lineas) if (linea.trim()) alEvento(JSON.parse(linea));
    }
    if (pendiente.trim()) alEvento(JSON.parse(pendiente));
  },
};
