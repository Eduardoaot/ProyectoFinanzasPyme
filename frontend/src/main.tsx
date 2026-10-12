import "@fontsource-variable/inter";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { aplicarTamanoTexto, leerTamanoTexto } from "./lib/tamanoTexto";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/layout.css";
import "./styles/chat.css";
import "./styles/paginas.css";
import "./styles/sencillo.css";
import "./styles/emergente.css";

// El tamaño de texto elegido se aplica antes de pintar, para que no "brinque" al cargar.
aplicarTamanoTexto(leerTamanoTexto());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
