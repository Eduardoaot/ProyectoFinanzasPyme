import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Loader2, Store } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Aviso, Logo } from "../components/ui/basicos";
import { useSesion } from "../context/Sesion";
import { api } from "../lib/api";
import type { Sesion } from "../lib/tipos";

const PREGUNTAS = [
  "¿Estoy ganando?",
  "¿Qué producto me deja más?",
  "¿Dónde gasto demasiado?",
  "¿Me va a alcanzar el efectivo?",
];

const DEMOS = [
  { email: "ana.ruiz@example.com", nombre: "Papelería El Lápiz Feliz", quien: "Ana · CDMX" },
  { email: "lupita.martinez@example.com", nombre: "Abarrotes Doña Lupita", quien: "Lupita · Guadalajara" },
  { email: "sofia.herrera@example.com", nombre: "Boutique Brisa", quien: "Sofía · Puebla" },
  { email: "carlos.mendez@example.com", nombre: "Contador (3 negocios)", quien: "Carlos · solo lectura" },
];

function PanelMarca() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % PREGUNTAS.length), 2600);
    return () => clearInterval(t);
  }, []);
  return (
    <section className="acceso-marca">
      {[
        { c: "#4a90d9", w: 420, x: "-10%", y: "-12%" },
        { c: "#2f6fb3", w: 360, x: "55%", y: "60%" },
        { c: "#7cb6ec", w: 220, x: "70%", y: "5%" },
      ].map((m, k) => (
        <motion.span
          key={k}
          className="mancha"
          style={{ background: m.c, width: m.w, height: m.w, left: m.x, top: m.y }}
          animate={{ x: [0, 40, -20, 0], y: [0, -30, 20, 0] }}
          transition={{ duration: 16 + k * 4, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}
      <div style={{ position: "relative" }}>
        <Logo tamano={42} />
      </div>
      <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 18 }}>
        <h1>
          Las finanzas de tu tienda, <em>claras</em> en 30 segundos.
        </h1>
        <p className="lema">
          Sube tus Excel de ventas, compras y gastos. Te mostramos cuánto ganas, qué producto te deja más y si te va a
          alcanzar el efectivo, sin palabras de contador.
        </p>
        <div className="pregunta-rotativa" aria-live="polite">
          <AnimatePresence mode="wait">
            <motion.span key={i} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -18 }} transition={{ duration: 0.4 }}>
              “{PREGUNTAS[i]}”
            </motion.span>
          </AnimatePresence>
        </div>
      </div>
      <motion.div className="mini-panel" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
        <div className="fila-entre" style={{ marginBottom: 12 }}>
          <span style={{ color: "#9eabba", fontSize: 13 }}>Así se ve la tendencia de tu negocio</span>
          <span className="chip" style={{ background: "rgb(255 255 255 / 0.06)", borderColor: "transparent", color: "#9eabba" }}>ilustración</span>
        </div>
        <svg viewBox="0 0 300 80" width="100%" height="80" aria-hidden="true">
          <defs>
            <linearGradient id="g-acceso" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#4a90d9" stopOpacity="0.45" />
              <stop offset="1" stopColor="#4a90d9" stopOpacity="0" />
            </linearGradient>
          </defs>
          <motion.path d="M0 62 C30 58 45 40 75 44 S120 60 150 38 S200 20 230 28 S275 12 300 8 L300 80 L0 80 Z" fill="url(#g-acceso)"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1, duration: 1 }} />
          <motion.path d="M0 62 C30 58 45 40 75 44 S120 60 150 38 S200 20 230 28 S275 12 300 8" fill="none" stroke="#7cb6ec" strokeWidth="2.5"
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.6, duration: 1.6, ease: "easeInOut" }} />
        </svg>
      </motion.div>
      <p className="pie-marca mini" style={{ color: "#5f6b79", position: "relative" }}>
        El sistema calcula todas las cifras; la IA solo las explica. Orientación general, no asesoría financiera.
      </p>
    </section>
  );
}

export function Acceso() {
  const { entrar } = useSesion();
  const [modo, setModo] = useState<"entrar" | "registro">("entrar");
  const [cargando, setCargando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [esContador, setEsContador] = useState(false);
  const [form, setForm] = useState({ nombre: "", email: "", password: "", nombre_negocio: "", giro: "Abarrotes", ciudad: "" });
  const campo = (k: keyof typeof form) => ({
    value: form[k],
    onChange: (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value })),
  });

  const ingresar = async (email: string, password: string, clave: string) => {
    setCargando(clave);
    setError(null);
    try {
      entrar(await api.post<Sesion>("/auth/login", { email, password }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCargando(null);
    }
  };

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    if (modo === "entrar") return ingresar(form.email, form.password, "form");
    setCargando("form");
    setError(null);
    try {
      const { nombre, email, password } = form;
      const cuerpo = esContador
        ? { nombre, email, password, es_contador: true }
        : { ...form, ciudad: form.ciudad || null };
      entrar(await api.post<Sesion>("/auth/registro", cuerpo));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCargando(null);
    }
  };

  return (
    <div className="acceso">
      <PanelMarca />
      <section className="acceso-form">
        <motion.div className="caja" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }}>
          <div className="pila" style={{ gap: 6 }}>
            <h2>{modo === "entrar" ? "Bienvenido de vuelta" : "Crea tu cuenta"}</h2>
            <p className="muted pequeno justificado">
              {modo === "entrar"
                ? "Entra con tu correo o prueba una de las tiendas de demostración."
                : "Registra tu negocio. Después te guiamos para subir tu primer Excel."}
            </p>
          </div>

          {modo === "entrar" && (
            <>
              <div className="demo-cuentas">
                {DEMOS.map((d, k) => (
                  <motion.button key={d.email} type="button" className="demo-cuenta" onClick={() => ingresar(d.email, "Demo2026!", d.email)}
                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + k * 0.07 }} disabled={!!cargando}>
                    <strong className="fila" style={{ gap: 6 }}>
                      {cargando === d.email ? <Loader2 size={14} className="girando" /> : <Store size={14} color="var(--celeste)" />}
                      {d.nombre}
                    </strong>
                    <span>{d.quien}</span>
                  </motion.button>
                ))}
              </div>
              <div className="separador">o con tu correo</div>
            </>
          )}

          <form className="pila" style={{ gap: 14 }} onSubmit={enviar}>
            <AnimatePresence initial={false}>
              {modo === "registro" && (
                <motion.div className="pila" style={{ gap: 14, overflow: "hidden" }} initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                  <div className="campo">
                    <label htmlFor="nombre">Tu nombre</label>
                    <input id="nombre" className="input" required minLength={2} {...campo("nombre")} />
                  </div>
                  <label className="casilla-contador">
                    <input type="checkbox" checked={esContador} onChange={(e) => setEsContador(e.target.checked)} />
                    <span>
                      <strong>Soy contador</strong>
                      <span className="muted pequeno">No tengo negocio propio: solo voy a revisar los negocios que me inviten.</span>
                    </span>
                  </label>
                  {!esContador && (
                    <>
                      <div className="campo">
                        <label htmlFor="negocio">Nombre de tu negocio</label>
                        <input id="negocio" className="input" required minLength={2} {...campo("nombre_negocio")} />
                      </div>
                      <div className="grid grid-2" style={{ gap: 12 }}>
                        <div className="campo">
                          <label htmlFor="giro">Giro</label>
                          <select id="giro" className="select" {...campo("giro")}>
                            {["Abarrotes", "Miscelánea", "Papelería", "Ropa y accesorios", "Frutería", "Farmacia", "Otro comercio"].map((g) => (
                              <option key={g}>{g}</option>
                            ))}
                          </select>
                        </div>
                        <div className="campo">
                          <label htmlFor="ciudad">Ciudad</label>
                          <input id="ciudad" className="input" {...campo("ciudad")} />
                        </div>
                      </div>
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
            <div className="campo">
              <label htmlFor="email">Correo</label>
              <input id="email" type="email" className="input" required autoComplete="email" {...campo("email")} />
            </div>
            <div className="campo">
              <label htmlFor="password">Contraseña</label>
              <input id="password" type="password" className="input" required minLength={modo === "registro" ? 8 : 1}
                autoComplete={modo === "entrar" ? "current-password" : "new-password"} {...campo("password")} />
            </div>
            {error && <Aviso tipo="error">{error}</Aviso>}
            <button className="btn primario" style={{ height: 46 }} disabled={!!cargando}>
              {cargando === "form" ? <Loader2 size={18} className="girando" /> : <ArrowRight size={18} />}
              {modo === "entrar" ? "Entrar" : "Crear cuenta"}
            </button>
          </form>
          <p className="pequeno centrado muted">
            {modo === "entrar" ? "¿Tu negocio aún no está registrado? " : "¿Ya tienes cuenta? "}
            <button type="button" className="btn fantasma chico" style={{ display: "inline-flex" }}
              onClick={() => { setModo(modo === "entrar" ? "registro" : "entrar"); setError(null); }}>
              {modo === "entrar" ? "Crear cuenta" : "Entrar"}
            </button>
          </p>
        </motion.div>
      </section>
    </div>
  );
}
