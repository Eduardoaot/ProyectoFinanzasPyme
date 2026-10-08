# Proyecciones, Impuestos y Deudas

Tres apartados que miran hacia adelante: **¿cómo me va a ir?**, **¿cuánto debo al SAT?** y **¿cuánto debo y cuándo termino de pagar?**
Rama: `feature/preditcivo`. Todo cálculo es determinista y vive en código; Clara (el LLM) solo redacta con las cifras ya calculadas.

## Cómo funciona Clara en estos apartados

Cada apartado arma un JSON con cifras **ya calculadas y ya formateadas** (`datos_para_clara`). Clara recibe la instrucción de explicarlas en máximo 5 frases y de usar solo esos números.
Si su texto trae una cifra que no está en el JSON, se **descarta completo** y se muestra la plantilla determinista (`backend/app/chat/apartados.py`). Sin Ollama funciona igual, con la plantilla.
Las alertas predictivas pasan por la misma guardia de cifras que el resto (`alerts/redaccion.py`, parámetro `redactar_ia=true`).

## Datos nuevos (migración `0003`)

| Tabla | Columnas nuevas |
|---|---|
| `empresas` | `tipo_persona`, `factura_a_morales`, `pct_ventas_morales`, `tiene_trabajadores`, `coeficiente_utilidad`, `minimo_seguridad` (null = 15 días de gastos fijos), `fondo_emergencia` |
| `productos_cat` | `tasa_iva` (null = sugerida por categoría), `lead_time_dias` (null = 3), `empaque` (null = 1) |
| `gastos_operativos` | `tiene_cfdi`, `medio_pago`, `uso` |
| `deudas` (nueva) | acreedor, tipo, montos, tasas, plazo, pago, límite, corte, día de pago, comisiones, moratoria, uso, estado |
| `pagos_deuda` (nueva) | fecha, monto, capital, interés, IVA |

La migración es idempotente (en una base nueva, `0001` ya crea todo desde `models.py`). Para una base existente: `alembic upgrade head`.

## Parámetros fiscales

`backend/app/impuestos/parametros_fiscales.json`, con **año de vigencia**. Para 2027 se agrega la llave `"2027"` sin tocar el código; si falta un año se usa el más reciente anterior.
Incluye IVA (0 % / 16 %, tope de efectivo $2,000, categorías a tasa 0), tabla RESICO mensual, tarifa del art. 96 LISR, tasa de personas morales, PTU, depreciación y topes de deducción.

> **Verificar antes de producción:** la tarifa del art. 96 cargada es la mensual publicada para 2024-2025 y se debe contrastar con el Anexo 8 de la RMF 2026. Está aislada en el JSON justo para eso.

## Supuestos (documentados a propósito)

- **Ventas cobradas el día en que se registran** (comercio al contado). Compras y gastos, pagados el día en que se registran.
- **Los precios y costos incluyen IVA.** `base = precio / (1 + tasa)`.
- **Compras de mercancía**: se asume CFDI y pago bancarizado (no existe ese dato por compra). Los **gastos** sí llevan `tiene_cfdi`, `medio_pago` y `uso`, editables en la pantalla de Impuestos.
- **Gastos importados** desde Excel quedan con factura y transferencia por defecto (el Excel no trae esos datos); se corrigen en "¿Esto se puede deducir?".
- **Pagos de deuda históricos no entran al efectivo actual** (el efectivo se calcula con ventas, compras y gastos, como en el resto de la app); los pagos futuros sí entran al flujo proyectado.
- **Pesimista / optimista** = pronóstico ∓ 1.28 σ (nivel de confianza ≈ 80 %). En el efectivo, la banda crece con √días y solo cuenta la parte de las ventas que se convierte en caja (margen bruto − gastos variables).
- **Presupuesto de compra** = efectivo actual − mínimo de seguridad. Si no alcanza, se compra primero lo que más ganancia diaria genera (ganancia por unidad × demanda) y se avisa qué posponer.
- **Reparto de la utilidad**: impuestos → deuda (obligatoria + 20 % del remanente como pago extra si hay deuda con tasa > 30 %) → fondo de emergencia (meta 3 × (fijos + deuda), en 6 meses) → reinversión (25 % del remanente) → retiro.
- **Deudas**: el IVA de intereses (16 %) se cobra sobre los intereses y sale del pago. Tarjetas pagan el mínimo Banxico cada mes (el mayor entre 1.5 % del saldo + intereses + IVA y 1.25 % del límite).
  Avalancha y bola de nieve usan el mismo monto mensual (pagos programados del primer mes + extra) y **lo que se libera al terminar una deuda se reutiliza**.

## Endpoints (todos bajo `/api/empresas/{id}`, todos con aislamiento por empresa)

| Método y ruta | Qué hace |
|---|---|
| `GET /proyecciones?semanas=4\|8\|12` | Pronóstico, utilidad, efectivo diario, equilibrio, inventario, consejos y alertas |
| `POST /proyecciones/escenario` | "¿Qué pasa si…?": recalcula sin guardar |
| `GET /proyecciones/clara` · `/impuestos/clara` · `/deudas/clara` | Explicación de Clara con guardia de cifras |
| `GET /impuestos?mes=YYYY-MM` | ISR + IVA del mes, mes por mes, calendario, comparador de régimen, PTU |
| `GET /impuestos/gastos?mes=` | Clasificador de deducciones con el motivo de cada gasto |
| `PUT /impuestos/configuracion` | Persona, régimen, facturación a morales, trabajadores |
| `PATCH /gastos/{id}/fiscal` · `PATCH /productos/{id}/parametros` | Factura/forma de pago/uso del gasto · IVA, entrega y empaque del producto |
| `GET /deudas?extra=` | Tarjetas, KPIs, estrategias, gráficas y alertas |
| `POST/PUT/DELETE /deudas`, `POST /deudas/{id}/liquidar`, `POST/GET /deudas/{id}/pagos` | CRUD y abonos (solo el rol `dueno` escribe) |
| `GET /deudas/{id}/amortizacion` · `/ahorro?extra=` · `/deudas/simulador/pago` | Tabla de amortización, ahorro por pago extra, "¿nunca baja?" |

## Cómo probar cada apartado

1. Backend: `cd backend && python -m pytest` (incluye `test_proyecciones.py`, `test_impuestos.py`, `test_deudas_formulas.py`, `test_predictivo_api.py`).
2. Frontend: `cd frontend && npm test` (incluye `predictivo.test.tsx`, que usa respuestas reales de la API; se regeneran con `python -m scripts.exportar_fixtures_front`).
3. Con la app corriendo e iniciando sesión con las cuentas de demostración (contraseña `Demo2026!`):
   - **Proyecciones** (`/proyecciones`): `ana.ruiz@example.com` (papelería, sana). Mueve "Si vendo −30 %" y mira cómo cambian la utilidad y el efectivo. `carlos.mendez@example.com` → Boutique: sale la alerta roja "tu utilidad no cubre impuestos y deudas" con el faltante exacto.
   - **Impuestos** (`/impuestos`): papelería = RESICO (los gastos no se deducen para ISR); abarrotes = vende mucho a IVA 0 % y casi no paga IVA; boutique = Actividades Empresariales (compara contra RESICO). En "¿Esto se puede deducir?" cambia un gasto a "con factura" y baja "Dinero que estás perdiendo".
   - **Deudas** (`/deudas`): papelería (sana), abarrotes (apretada, con la tarjeta BBVA de pago mínimo $567.84) y boutique (en riesgo: tarjeta al 88 % y préstamo al 78 % anual, cobertura < 1).

## Casos de aceptación cubiertos por pruebas

| Caso | Resultado |
|---|---|
| Punto de equilibrio trimestral 9,670 / 0.5568 | ≈ $17,367 (≈ $5,789 al mes); en la papelería demo sale $5,789.65 |
| Pronóstico de octubre (venta base $872.37 × 31 = $27,043) | Queda dentro del rango pesimista–optimista mostrado |
| RESICO con ingresos de $26,750 | Tasa 1.10 % → ISR ≈ $294 |
| Crédito de $60,000 al 28 % a 24 meses | Pago ≈ $3,293 (sin IVA) |
| Tarjeta de $8,450 al 54 %, límite $20,000 | Pago mínimo $567.84 |
