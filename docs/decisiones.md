# Decisiones técnicas

Registro breve de las decisiones importantes y su porqué (proyecto de aprendizaje).

## Cambios de stack respecto a la versión inicial de CLAUDE.md (aprobados el 2026-10-06)

| Antes | Ahora | Motivo |
|---|---|---|
| Next.js | **React + Vite** | Es una SPA detrás de login: no necesita SSR y Vite es más simple de correr. |
| PostgreSQL | **MySQL 8** local | Es el motor que ya está instalado en el equipo de desarrollo. SQLAlchemy Core y SQL portable (`DATE()`, fechas ISO) permiten cambiar de motor con una variable de entorno. |
| API de Claude | **Ollama local (`llama3.2:3b`)** | Gratuito y privado: los datos financieros no salen de la computadora. |

## El código calcula, la IA explica (principio 2)

- El chatbot no le pide números al LLM. El flujo es: **intención y periodo** (reglas; el LLM solo clasifica si ninguna regla aplica) → **hechos** calculados con el mismo servicio que alimenta el dashboard → el LLM redacta 2–4 oraciones de interpretación → **guardia de cifras** (`app/llm/guardia.py`).
- La guardia compara cada número del texto generado contra las cifras permitidas y descarta las oraciones con números inventados. Hay pruebas con un LLM falso que inventa "250%" o "$1,234,567".
- La guardia no detecta errores de *significado* con cifras válidas: un modelo de 3B parámetros llegó a llamar "utilidad bruta" a la pérdida neta. La mitigación es enviarle datos breves y sin ambigüedad y una **explicación calculada por código** (p. ej., "gastos +59.6% vs ventas +30.0%"), para que no tenga que deducirla.
- Las secciones con cifras de cada respuesta las arma el código en Markdown. El LLM solo escribe la sección "Lo que significa".
- Si Ollama no responde, todo funciona con textos de plantilla deterministas.

## Rendimiento de la IA local

`llama3.2:3b` corre en CPU a ~7–8 tokens/s en el equipo de desarrollo. Por eso:
- El chat responde en **streaming**: las cifras aparecen al instante y la interpretación llega palabra por palabra (unos 15 s en total).
- Las alertas se muestran primero con su plantilla. La versión redactada por IA se pide en segundo plano (una sola llamada para todas) y queda en caché.
- Caché común (`app/llm/cache.py`, 2026-10-09) para alertas y para «Clara te lo explica». Funciona así:
  - Con los mismos datos se devuelve la misma respuesta, sin volver a llamar al modelo.
  - Dos peticiones iguales simultáneas (React `StrictMode` pide dos veces en desarrollo) hacen una sola llamada.
  - Una respuesta que la guardia rechazó también se guarda, para no esperar otra vez al modelo por un texto que se volvería a descartar. Solo se reintenta cuando Ollama no respondió.
  - El tamaño está acotado.
  - Antes, cada visita a Proyecciones, Impuestos o Deudas costaba de 10 a 20 s de modelo, y Ollama atiende una petición a la vez, así que se formaba una fila.
- `keep_alive: 30m` en las llamadas a Ollama: el modelo sigue cargado entre peticiones (por defecto lo descarga a los 5 min).
- El chat flotante y la página Resumen se cargan de forma diferida: la pantalla de inicio de sesión ya no descarga Recharts ni el lector de Markdown (el archivo principal bajó de 827 KB a 314 KB).

## Modelo de datos

- Se combinaron las tablas pedidas (usuarios, ventas, productos, **compras de producto**, **gastos operativos**) con las de CLAUDE.md §5.
- `gastos_fijos` y `gastos_variables` se unificaron en **`gastos_operativos`** con un campo `tipo` (`fijo` | `variable`). Es un libro diario fechado: la renta de cada mes es un registro, lo que facilita el flujo de efectivo y la importación desde Excel.
- En un inicio existía `tipo='retiro'` para registrar el dinero que el dueño saca para uso personal. Se eliminó (oct 2026): confundía a los usuarios no contadores, complicaba la importación y duplicaba el gasto variable en el flujo. Si un archivo trae un concepto como "Retiro personal", se clasifica como gasto variable. El polo opuesto era "gasto" vs "no gasto", no "gasto del negocio" vs "retiro".
- `compras_producto` alimenta el flujo de efectivo (lo que se pagó a proveedores); el costo de ventas sale de `historial_ventas.costo_unitario`.
- `empresas.umbrales_alerta` (JSON) guarda los umbrales personalizados de cada negocio, así no hay umbrales fijos en el código.
- El esquema tiene una sola fuente, `app/db/models.py`. De ahí salen el SQL de MySQL, la migración de Alembic y la base de pruebas.

## Ingesta

- Staging: el archivo leído se guarda como JSON temporal (24 h) identificado por un token ligado a la empresa. Nada llega a las tablas finales sin confirmación.
- La carga ocurre en una sola transacción y cada fila lleva `id_importacion`, así que **deshacer** borra exactamente esa carga.
- **El stock sale del catálogo de productos.** Importar ventas o compras históricas no lo modifica, porque el catálogo ya refleja el inventario de hoy y descontar ventas pasadas lo contaría dos veces.
- Seguridad: solo `.xlsx` y `.csv`, tamaño máximo, firma ZIP para Excel, sin evaluar fórmulas (`data_only=True`) y limpieza de textos que empiezan con `= + - @` (inyección CSV).

## Seguridad y multiempresa

- JWT con contraseñas PBKDF2 (biblioteca estándar, sin dependencias con binarios).
- Toda ruta `/empresas/{id}` pasa por `empresa_autorizada`, que verifica la membresía del usuario autenticado. Si no la tiene responde **404** (no 403), para no revelar que la empresa existe.
- Rol `consulta` (p. ej., el contador): solo lectura. No puede importar ni cambiar umbrales (`empresa_editable`).
- Invitar al contador (2026-10-09): el dueño, desde **Mi equipo**, da acceso de `consulta` a una cuenta **que ya existe**, escribiendo su correo, y puede quitárselo. No hay invitaciones pendientes ni envío de correos: es lo más simple para el MVP. El registro tiene la opción «Soy contador», que crea la cuenta sin negocio propio. El dueño también puede volver **dueño** a un invitado (mismos permisos que él, incluido administrar Mi equipo) y regresarlo después a «solo ver». Nadie puede cambiar ni quitar su propio acceso, así que ningún negocio se queda sin dueño. Riesgo aceptado: un segundo dueño podría quitarle el acceso al primero; por eso la interfaz pide confirmar antes de volver dueño a alguien.
- Perfil (2026-10-09): el menú de la cuenta (arriba a la derecha) muestra nombre y correo y lleva a **Mi perfil**, donde se cambia el nombre y la contraseña. El correo no se puede cambiar, porque es con el que otros invitan a la persona. Si la contraseña actual es incorrecta se responde 400 y no 401, para que el frontend no cierre la sesión.
- Los logs no incluyen cifras ni contenido enviado al LLM.

## Proyecciones, impuestos y deudas (aprobado el 2026-10-08)

Los impuestos, que CLAUDE.md §3 dejaba para la fase 2, se adelantan a petición expresa del dueño del proyecto, junto con proyecciones y deudas. El pronóstico base es estadístico y determinista (promedio de 8 semanas × índice por día de la semana + tendencia limitada a ±15 %), no un prompt. Detalle, supuestos y cómo probar: [predictivo.md](predictivo.md).

## Pronóstico

- `ForecastService` (Protocol) con la implementación `PromedioMovil(ventana=30)`, que también produce una banda de ±1.28σ.
- El endpoint `GET /empresas/{id}/forecast` y la vista `v_ventas_diarias` ya están listos para que la fase 2 conecte Prophet o ARIMA sin cambiar la API.

## Datos de demostración

- La simulación es de inventario: ventas diarias Poisson con estacionalidad (regreso a clases, Día de las Madres, Buen Fin, Navidad) y tendencia. Al llegar al punto de reorden se registra una compra, así que ventas, compras y stock son coherentes entre sí.
- La Papelería cuadra **exactamente** con el caso base de §12. Ese caso tiene un margen bruto del 55.9%, alto para una papelería real, pero se respetó porque es el criterio de calidad del proyecto.
- Los escenarios de alerta se construyen sin romper la coherencia. Por ejemplo, "por agotarse" reduce la última compra del producto, después de la cual el stock solo baja, de modo que nunca queda negativo.

## Inicio sencillo (aprobado el 2026-10-09)

Pensado para la dueña de una tienda muy pequeña (una señora de 80 años con una frutería) que no lee gráficas, no conoce términos de negocio y no sabe qué preguntar.

- **Es lo primero que se ve al entrar.** Va sin menú lateral, con letra grande y una sola columna. El panel de siempre queda como **modo avanzado**, sin cambios. Se recuerda el último modo que la persona eligió **con un botón** («Ver todo con detalle» o «Volver al Inicio sencillo»); entrar a «Ver detalles» no cambia su modo.
- **Rutas:** `/` es el Inicio sencillo y el Resumen del modo avanzado se movió a `/resumen`.
- **Contenido:**
  - ¿Cómo te fue?, con semáforo y la cuenta Vendiste − Gastaste = Te quedó.
  - Una gráfica de barras de 6 meses: sin eje Y y con el valor sobre cada barra, porque quien la lee no interpreta escalas.
  - Los productos que más dejan, con «¿te queda?».
  - Lo que viene: venta esperada, si alcanza el dinero y qué comprar.
  - Mini tarjetas de impuestos y deudas.
  - Cada tarjeta tiene «¿Qué es esto?» y «Ver detalles», que lleva a la página avanzada.
- **`GET /empresas/{id}/inicio`** junta en una llamada (~0.6 s) las cifras de los servicios que ya existen; no calcula nada nuevo. La frase del semáforo la arma el código, con los mismos umbrales que las alertas.
- **Ventana de Clara:**
  - Muestra una explicación fija escrita por personas, preguntas ya hechas por tema y un campo para escribir o dictar. La conversación es aparte del chat flotante.
  - **Primero responde el sistema** (`usar_ia: false`): sale al instante y siempre es correcto.
  - El botón «Explícamelo con otras palabras» pide la redacción de la IA en **modo sencillo** y la marca como «Redactado por IA».
  - Motivo: el modelo de 3B, aun con la guardia de cifras, daba consejos con lógica equivocada que la guardia no puede detectar. Ejemplos: «para pagar menos impuestos, aumenta tus ingresos» y «los gastos sin factura se acreditan». Para quien confía en todo lo que lee, la respuesta principal no puede depender de eso.
  - Algunas preguntas guía muestran un texto y le mandan al chat otra frase que su detector de intenciones sí reconoce. Por ejemplo, «¿Qué tengo que comprar?» se envía como «¿Qué productos tengo que resurtir?».

## Interfaz

- Paleta: blanco, negro y azul celeste apagados. Los colores de las gráficas se validaron para daltonismo en modo claro y oscuro: celeste = ventas/entradas, naranja = costos/gastos/salidas, aqua = utilidad. Nunca se generan colores extra: más de 6 categorías se agrupan en "Otros".
- Tipografía: una sola familia (Inter) y una escala fija. Los párrafos de lectura van justificados con guiones automáticos, las cifras usan números tabulares y las tarjetas KPI van centradas.
- El semáforo siempre combina ícono, texto y color, nunca solo color.
- Voz: Web Speech API (`es-MX`) del navegador, para reconocimiento y síntesis, sin costo ni dependencias.
