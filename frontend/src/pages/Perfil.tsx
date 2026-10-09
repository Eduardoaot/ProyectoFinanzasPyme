import { Check, KeyRound, Loader2, LogOut, Save, Store, UserRound } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Aviso, Tarjeta, TituloTarjeta } from "../components/ui/basicos";
import { Pagina } from "../components/ui/Pagina";
import { useSesion } from "../context/Sesion";
import { api } from "../lib/api";
import type { Usuario } from "../lib/tipos";

type Estado = { tipo: "ok" | "error"; texto: string } | null;

function DatosPersonales() {
  const { usuario, actualizarUsuario } = useSesion();
  const [nombre, setNombre] = useState(usuario?.nombre ?? "");
  const [guardando, setGuardando] = useState(false);
  const [estado, setEstado] = useState<Estado>(null);
  const cambiado = nombre.trim() !== usuario?.nombre && nombre.trim().length >= 2;

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    setEstado(null);
    try {
      actualizarUsuario(await api.patch<Usuario>("/auth/yo", { nombre: nombre.trim() }));
      setEstado({ tipo: "ok", texto: "Guardamos tu nombre." });
    } catch (err) {
      setEstado({ tipo: "error", texto: (err as Error).message });
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Tarjeta interactiva={false}>
      <TituloTarjeta icono={UserRound} titulo="Tus datos" />
      <form className="pila" style={{ gap: 14 }} onSubmit={guardar}>
        <div className="campo">
          <label htmlFor="perfil-nombre">Nombre</label>
          <input id="perfil-nombre" className="input" required minLength={2} maxLength={120} value={nombre}
            onChange={(e) => setNombre(e.target.value)} autoComplete="name" />
        </div>
        <div className="campo">
          <label htmlFor="perfil-correo">Correo</label>
          <input id="perfil-correo" className="input" value={usuario?.email ?? ""} readOnly aria-describedby="perfil-correo-ayuda" />
          <span id="perfil-correo-ayuda" className="mini muted">Es con el que entras y con el que otros te invitan a sus negocios.</span>
        </div>
        {estado && <Aviso tipo={estado.tipo === "error" ? "error" : "info"}>{estado.texto}</Aviso>}
        <button className="btn primario" disabled={!cambiado || guardando} style={{ alignSelf: "flex-start" }}>
          {guardando ? <Loader2 size={16} className="girando" /> : <Save size={16} />} Guardar cambios
        </button>
      </form>
    </Tarjeta>
  );
}

function CambiarContrasena() {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [estado, setEstado] = useState<Estado>(null);
  const noCoinciden = confirmar.length > 0 && nueva !== confirmar;

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    if (noCoinciden) return;
    setGuardando(true);
    setEstado(null);
    try {
      await api.post("/auth/password", { actual, nueva });
      setActual("");
      setNueva("");
      setConfirmar("");
      setEstado({ tipo: "ok", texto: "Listo: cambiamos tu contraseña. Úsala la próxima vez que entres." });
    } catch (err) {
      setEstado({ tipo: "error", texto: (err as Error).message });
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Tarjeta interactiva={false} retraso={0.05}>
      <TituloTarjeta icono={KeyRound} titulo="Cambiar contraseña" sub="Mínimo 8 caracteres." />
      <form className="pila" style={{ gap: 14 }} onSubmit={guardar}>
        <div className="campo">
          <label htmlFor="pass-actual">Contraseña actual</label>
          <input id="pass-actual" type="password" className="input" required autoComplete="current-password"
            value={actual} onChange={(e) => setActual(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="pass-nueva">Contraseña nueva</label>
          <input id="pass-nueva" type="password" className="input" required minLength={8} maxLength={128} autoComplete="new-password"
            value={nueva} onChange={(e) => setNueva(e.target.value)} />
        </div>
        <div className="campo">
          <label htmlFor="pass-confirmar">Repite la contraseña nueva</label>
          <input id="pass-confirmar" type="password" className="input" required autoComplete="new-password"
            value={confirmar} onChange={(e) => setConfirmar(e.target.value)} aria-invalid={noCoinciden} />
          {noCoinciden && <span className="mini" style={{ color: "var(--bad-ink)" }}>Las dos contraseñas nuevas no coinciden.</span>}
        </div>
        {estado && <Aviso tipo={estado.tipo === "error" ? "error" : "info"}>{estado.texto}</Aviso>}
        <button className="btn primario" disabled={guardando || noCoinciden || !actual || nueva.length < 8} style={{ alignSelf: "flex-start" }}>
          {guardando ? <Loader2 size={16} className="girando" /> : <KeyRound size={16} />} Cambiar contraseña
        </button>
      </form>
    </Tarjeta>
  );
}

export function Perfil() {
  const { empresas, idEmpresa, cambiarEmpresa, salir } = useSesion();

  return (
    <Pagina titulo="Mi perfil" descripcion="Tus datos de acceso y los negocios que puedes ver."
      acciones={<button className="btn" onClick={salir}><LogOut size={16} /> Cerrar sesión</button>}>
      <div className="grid grid-2 perfil">
        <DatosPersonales />
        <CambiarContrasena />
      </div>
      <Tarjeta interactiva={false} retraso={0.1}>
        <TituloTarjeta icono={Store} titulo="Tus negocios" sub={empresas.length === 1 ? "Tienes acceso a 1 negocio." : `Tienes acceso a ${empresas.length} negocios.`} />
        <ul className="lista-accesos">
          {empresas.map((e) => (
            <li key={e.id_empresa}>
              <div className="datos">
                <strong>{e.nombre_negocio}</strong>
                <span className="muted pequeno">{e.giro}{e.ciudad ? ` · ${e.ciudad}` : ""}</span>
              </div>
              <span className={`chip ${e.rol === "dueno" ? "celeste" : ""}`}>{e.rol === "dueno" ? "Dueño" : "Solo puedes ver"}</span>
              {e.id_empresa === idEmpresa ? (
                <span className="chip ok"><Check size={13} aria-hidden="true" /> Abierto</span>
              ) : (
                <button type="button" className="btn chico" onClick={() => cambiarEmpresa(e.id_empresa)}>Abrir</button>
              )}
            </li>
          ))}
        </ul>
      </Tarjeta>
    </Pagina>
  );
}
