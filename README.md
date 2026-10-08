# Cuentas Claras

Plataforma de inteligencia financiera para tiendas pequeñas en México (abarrotes, papelerías, boutiques…). El dueño sube sus Excel y ve en menos de 30 segundos si está ganando, qué producto le deja más, dónde gasta de más y si le va a alcanzar el efectivo.

> **El código calcula, la IA explica.** Todas las cifras salen de SQL y Python. La IA local (Ollama) solo las redacta, y una *guardia de cifras* descarta cualquier oración que contenga un número que no venga de los datos.

| Capa | Tecnología |
|---|---|
| Frontend | React 19 + Vite + TypeScript, Recharts, Framer Motion, Web Speech API (voz en español) |
| Backend | Python 3.12+ · FastAPI · SQLAlchemy Core · Pydantic |
| Base de datos | MySQL 8 (SQLite solo para pruebas automáticas) |
| IA | Ollama local (`llama3.2:3b`) para mapear columnas y redactar alertas y respuestas |
| Pronóstico | `ForecastService` con promedio móvil (fase 1), listo para Prophet o ARIMA (fase 2) |

---

## 1. Requisitos

- Python 3.12 o superior (probado con 3.14)
- Node.js 20 o superior (probado con 24)
- MySQL 8.0 corriendo en local
- [Ollama](https://ollama.com) con el modelo descargado: `ollama pull llama3.2:3b`
  (es opcional: sin Ollama todo funciona con textos de plantilla)

## 2. Base de datos (MySQL)

El archivo **`database/cuentas_claras.sql`** crea la base `cuentas_claras` con todas las tablas, la vista `v_ventas_diarias` y los datos de demostración: 3 tiendas con 2 años de historia (octubre 2024 a septiembre 2026).

**Opción A: MySQL Workbench.** Abre *File → Open SQL Script*, elige `database/cuentas_claras.sql` y ejecútalo (⚡).

**Opción B: terminal.**
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p < database\cuentas_claras.sql
```

`database/schema.sql` trae solo el esquema, sin datos, para empezar en limpio.

## 3. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # y edita DATABASE_URL y JWT_SECRET
uvicorn app.main:app --reload --port 8000
```

La documentación interactiva de la API queda en http://localhost:8000/docs.

### Variables de entorno (`backend/.env`)

| Variable | Ejemplo | Para qué |
|---|---|---|
| `DATABASE_URL` | `mysql+pymysql://root:CLAVE@localhost:3306/cuentas_claras?charset=utf8mb4` | Conexión a MySQL |
| `JWT_SECRET` | 48 caracteres aleatorios | Firma de las sesiones. Genera uno con `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_EXPIRA_HORAS` | `12` | Duración de la sesión |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Servidor de Ollama |
| `OLLAMA_MODELO` | `llama3.2:3b` | Modelo local |
| `OLLAMA_TIMEOUT` | `120` | Segundos máximos por respuesta |
| `CORS_ORIGENES` | `["http://localhost:5173"]` | Origen del frontend |
| `MAX_ARCHIVO_MB` | `5` | Tamaño máximo de un Excel |

### Regenerar los datos de demostración

```powershell
cd backend
python -m scripts.generar_seed            # reescribe database/schema.sql y database/cuentas_claras.sql
python -m scripts.generar_seed --cargar   # además los inserta en DATABASE_URL
```

La generación es reproducible (semilla fija) y valida que cada tienda tenga al menos 700 ventas, 700 compras y 700 gastos.

### Migraciones

El esquema vive en `backend/app/db/models.py` y Alembic lo versiona:
```powershell
alembic upgrade head      # base vacía
alembic stamp head        # si cargaste cuentas_claras.sql (las tablas ya existen)
```

### Pruebas del backend

Desde la raíz del proyecto, ejecuta pytest con el entorno virtual del backend:
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

También puedes activar el entorno con `.\.venv\Scripts\Activate.ps1` y ejecutar `python -m pytest`. No uses `npm test` en `backend`: el proyecto de Node está en `frontend`.

## 4. Frontend

```powershell
cd frontend
npm install
npm run dev               # http://localhost:5173  (redirige /api al backend en :8000)
```

**La voz** (dictar con el micrófono y escuchar las respuestas en español) funciona en **Chrome y Edge**: la primera vez el navegador pide permiso para el micrófono.

## 5. Cuentas de demostración

Todas usan la contraseña **`Demo2026!`**. La pantalla de inicio tiene botones de acceso rápido.

| Usuario | Negocio | Qué muestra |
|---|---|---|
| ana.ruiz@example.com | Papelería El Lápiz Feliz (CDMX) | **Caso base de CLAUDE.md §12**: ene–sep 2026 ventas $170,000 · costo $75,000 · gastos $30,000 · utilidad $65,000 · margen 38.2%. Temporada de regreso a clases, caída en septiembre, calculadora con margen de 8% y cuaderno por agotarse |
| lupita.martinez@example.com | Abarrotes Doña Lupita (Guadalajara) | Margen neto bajo (~10%), Coca-Cola 2 L con margen de 6.8%, costo del huevo +14% sin subir el precio, leche por agotarse |
| sofia.herrera@example.com | Boutique Brisa (Puebla) | Temporadas (Día de las Madres, Buen Fin, Navidad), pérdida en septiembre, gastos que crecen más rápido que las ventas, compra de invierno y **flujo proyectado negativo** |
| carlos.mendez@example.com | Las tres (contador) | Acceso de **solo lectura** a varios negocios |

| Tabla | Papelería | Abarrotes | Boutique |
|---|---|---|---|
| Productos | 35 | 45 | 28 |
| Ventas | 11,357 | 24,856 | 3,216 |
| Compras de producto | 813 | 3,544 | 1,122 |
| Gastos operativos | 744 | 739 | 777 |

## 6. Pruebas

```powershell
cd backend;  pytest          # 82 pruebas: fórmulas, caso base, aislamiento, ingesta, chat y guardia
cd frontend; npm test        # 14 pruebas: formato, periodos, voz y componentes
```

Las pruebas del backend usan SQLite en memoria con el dataset completo y un LLM simulado, así que no requieren MySQL ni Ollama.

> Proyecciones, impuestos y deudas: ver [docs/predictivo.md](docs/predictivo.md). Después de actualizar el código ejecuta `alembic upgrade head` (migración `0003`).

## 7. Cómo subir un Excel (usuario nuevo)

1. Crea tu cuenta y entra a **Importar datos → Tutorial**.
2. Sube primero tu **catálogo de productos** (con tus existencias de hoy). Después sube ventas, compras y gastos.
3. Tu archivo puede tener títulos arriba, filas de totales o columnas con otros nombres ("P. Unitario", "Importe"). Puedes descargar una plantilla si no tienes formato.
4. Revisa cómo se entendieron tus columnas. La IA ve solo los encabezados y 5 filas de muestra.
5. Revisa qué filas tienen problemas (con número de fila y motivo) y confirma. Puedes **deshacer** cualquier carga desde el historial.

En `backend/tests/fixtures/` hay 5 archivos de ejemplo con formatos realistas (`.xlsx` y `.csv` con `;`, coma decimal, títulos, totales, duplicados y una fórmula maliciosa).

## 8. Estructura

```
backend/
  app/
    api/          rutas FastAPI, autenticación JWT, permisos por empresa
    finance/      fórmulas (§7), consultas SQL, servicio de KPIs/estado de resultados/flujo
    forecasting/  ForecastService (promedio móvil → Prophet/ARIMA)
    alerts/       reglas deterministas + redacción con LLM
    chat/         intención y periodo, hechos calculados, asistente "Clara"
    ingestion/    lectura segura, mapeo IA, limpieza, carga, plantillas
    llm/          cliente Ollama y guardia de cifras
    db/           esquema (fuente única) y conexión
  scripts/generar_seed.py
  tests/
frontend/src/
  pages/          Resumen, Finanzas, Productos, Flujo, Alertas, Importar, Asistente, Acceso
  components/     layout, chat (voz), gráficas, UI
  context/        sesión, periodo, chat
  lib/            api, formato, periodos, voz
database/         schema.sql y cuentas_claras.sql (generados)
docs/             decisiones.md y esquema.md
```

## 9. Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/auth/registro`, `/api/auth/login` | Cuenta y sesión |
| GET | `/api/empresas/{id}/resumen?desde&hasta` | KPIs, comparación y datos clave |
| GET | `/api/empresas/{id}/finanzas` | Estado de resultados, gastos y punto de equilibrio |
| GET | `/api/empresas/{id}/productos` | Margen por producto e inventario con semáforo |
| GET | `/api/empresas/{id}/flujo` | Entradas y salidas, saldo y proyección a 30 días |
| GET | `/api/empresas/{id}/forecast?serie&id_producto&dias` | Pronóstico (línea base; misma firma para fase 2) |
| GET | `/api/empresas/{id}/alertas?redactar_ia=true` | Alertas deterministas, redactadas por IA |
| PUT | `/api/empresas/{id}/umbrales` | Umbrales de alertas configurables |
| POST | `/api/empresas/{id}/chat` | Respuesta completa `{"answer": …}` |
| POST | `/api/empresas/{id}/chat/stream` | Respuesta en streaming (NDJSON) |
| POST | `/api/empresas/{id}/importaciones/analizar` → `/{token}/previsualizar` → `/{token}/confirmar` | Ingesta de Excel/CSV |
| DELETE | `/api/empresas/{id}/importaciones/{id_importacion}` | Deshacer una carga |

> Los consejos son orientativos y no constituyen asesoría financiera, contable ni fiscal.
