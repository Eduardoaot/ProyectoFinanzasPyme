import { AnimatePresence, motion } from "framer-motion";
import { Eye, Loader2, Mail, ShieldCheck, UserMinus, UserPlus, Users } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Aviso, Tarjeta, TarjetaCargando, TituloTarjeta } from "../components/ui/basicos";
import { Pagina } from "../components/ui/Pagina";
import { useSesion } from "../context/Sesion";
import { useApi } from "../hooks/useApi";
import { api } from "../lib/api";
import type { Acceso } from "../lib/tipos";

/** El dueño decide quién más puede ver su negocio (p. ej. su contador), siempre en modo "solo ver". */
export function Equipo() {
  const { empresa, empresas } = useSesion();
  const id = empresa?.id_empresa;
  const esDueno = empresas.find((e) => e.id_empresa === id)?.rol === "dueno";
  const accesos = useApi<Acceso[]>(id && esDueno ? `/empresas/${id}/accesos` : null);
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [ocupado, setOcupado] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  const invitar = async (e: FormEvent) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    setExito(null);
    try {
      const nuevo = await api.post<Acceso>(`/empresas/${id}/accesos`, { email: email.trim() });
      setExito(`Listo: ${nuevo.nombre} ya puede ver ${empresa?.nombre_negocio}. Solo tiene que entrar con su correo.`);
      setEmail("");
      accesos.recargar();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setEnviando(false);
    }
  };

  const conAviso = async (a: Acceso, accion: () => Promise<unknown>, mensaje?: string) => {
    setOcupado(a.id_usuario);
    setError(null);
    setExito(null);
    try {
      await accion();
      if (mensaje) setExito(mensaje);
      accesos.recargar();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setOcupado(null);
    }
  };

  const quitar = (a: Acceso) => {
    if (!window.confirm(`¿Quitarle el acceso a ${a.nombre}? Dejará de ver ${empresa?.nombre_negocio}.`)) return;
    conAviso(a, () => api.delete(`/empresas/${id}/accesos/${a.id_usuario}`));
  };

  const cambiarRol = (a: Acceso, rol: Acceso["rol"]) => {
    // Un dueño tiene los mismos permisos que tú, incluso para quitarte el acceso: se pide confirmar.
    if (rol === "dueno" && !window.confirm(
      `${a.nombre} podrá subir archivos, cambiar datos, invitar a otras personas y quitar accesos (incluso el tuyo). ¿Hacerlo dueño?`)) return;
    conAviso(a, () => api.patch(`/empresas/${id}/accesos/${a.id_usuario}`, { rol }),
      rol === "dueno" ? `${a.nombre} ahora es dueño y puede hacer cambios.` : `${a.nombre} ahora solo puede ver.`);
  };

  if (!esDueno) {
    return (
      <Pagina titulo="Mi equipo" descripcion="Quién puede ver este negocio.">
        <Aviso>Solo el dueño del negocio puede ver y cambiar quién tiene acceso. Tú tienes acceso de consulta: puedes ver todo, pero no cambiar nada.</Aviso>
      </Pagina>
    );
  }

  return (
    <Pagina titulo="Mi equipo"
      descripcion="Invita a tu contador o a alguien de confianza para que vea los números de tu negocio. Al principio solo puede ver; tú decides si también puede hacer cambios.">
      <div className="grid grid-2 equipo">
        <Tarjeta interactiva={false}>
          <TituloTarjeta titulo="Invitar a alguien" icono={UserPlus} sub="La persona debe tener ya una cuenta en Cuentas Claras." />
          <form className="pila" style={{ gap: 12 }} onSubmit={invitar}>
            <div className="campo">
              <label htmlFor="correo-invitado">Correo con el que se registró</label>
              <input id="correo-invitado" type="email" className="input" required placeholder="contador@ejemplo.com"
                value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <button className="btn primario" disabled={enviando || !email.trim()} style={{ alignSelf: "flex-start" }}>
              {enviando ? <Loader2 size={16} className="girando" /> : <Mail size={16} />} Darle acceso
            </button>
          </form>
          <AnimatePresence>
            {(error || exito) && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} style={{ marginTop: 12 }}>
                {error ? <Aviso tipo="error">{error}</Aviso> : <Aviso>{exito}</Aviso>}
              </motion.div>
            )}
          </AnimatePresence>
          <ul className="equipo-reglas muted pequeno">
            <li><Eye size={14} aria-hidden="true" /> Podrá ver reportes, gráficas, alertas, impuestos y deudas, y preguntarle a Clara.</li>
            <li><ShieldCheck size={14} aria-hidden="true" /> Con «Solo puede ver» no podrá subir archivos, borrar importaciones ni cambiar nada.</li>
            <li><UserMinus size={14} aria-hidden="true" /> Puedes quitarle el acceso cuando quieras, o volverlo dueño si quieres que también pueda hacer cambios.</li>
          </ul>
          <p className="muted pequeno">
            ¿Aún no tiene cuenta? Pídele que se registre y marque <strong>«Soy contador»</strong>; así no tiene que dar de alta un negocio.
          </p>
        </Tarjeta>

        <Tarjeta interactiva={false} retraso={0.05}>
          <TituloTarjeta titulo="Quién tiene acceso" icono={Users} />
          {accesos.error && <Aviso tipo="error">{accesos.error}</Aviso>}
          {!accesos.datos ? (
            <TarjetaCargando alto={120} />
          ) : (
            <ul className="lista-accesos">
              <AnimatePresence initial={false}>
                {accesos.datos.map((a) => (
                  <motion.li key={a.id_usuario} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, height: 0 }}>
                    <div className="datos">
                      <strong>{a.nombre}{a.eres_tu && <span className="muted"> (tú)</span>}</strong>
                      <span className="muted pequeno">{a.email}</span>
                    </div>
                    {a.eres_tu ? (
                      <span className="chip celeste">Dueño</span>
                    ) : (
                      <>
                        <select className="select select-rol" value={a.rol} disabled={ocupado === a.id_usuario}
                          onChange={(e) => cambiarRol(a, e.target.value as Acceso["rol"])} aria-label={`Permiso de ${a.nombre}`}>
                          <option value="consulta">Solo puede ver</option>
                          <option value="dueno">Dueño (puede cambiar todo)</option>
                        </select>
                        <button type="button" className="btn chico fantasma" onClick={() => quitar(a)} disabled={ocupado === a.id_usuario}
                          aria-label={`Quitar acceso a ${a.nombre}`}>
                          {ocupado === a.id_usuario ? <Loader2 size={14} className="girando" /> : <UserMinus size={14} />} Quitar
                        </button>
                      </>
                    )}
                  </motion.li>
                ))}
              </AnimatePresence>
              {accesos.datos.length === 1 && (
                <li className="muted pequeno">Por ahora solo tú puedes ver este negocio.</li>
              )}
            </ul>
          )}
        </Tarjeta>
      </div>
    </Pagina>
  );
}
