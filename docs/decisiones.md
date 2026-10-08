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

## Interfaz

- Paleta: blanco, negro y azul celeste apagados. Los colores de las gráficas se validaron para daltonismo en modo claro y oscuro: celeste = ventas/entradas, naranja = costos/gastos/salidas, aqua = utilidad. Nunca se generan colores extra: más de 6 categorías se agrupan en "Otros".
- Tipografía: una sola familia (Inter) y una escala fija. Los párrafos de lectura van justificados con guiones automáticos, las cifras usan números tabulares y las tarjetas KPI van centradas.
- El semáforo siempre combina ícono, texto y color, nunca solo color.
- Voz: Web Speech API (`es-MX`) del navegador, para reconocimiento y síntesis, sin costo ni dependencias.
