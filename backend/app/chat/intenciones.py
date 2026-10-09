"""Detección de intención y periodo en la pregunta del dueño.

Primero se usan reglas por palabras clave (rápidas y predecibles). Solo si ninguna regla
coincide se le pide al LLM que clasifique la pregunta en una de las intenciones conocidas.
"""

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

from app.chat import glosario
from app.finance.periodos import MESES, fin_de_mes, sumar_meses
from app.llm.ollama import get_llm

INTENCIONES: dict[str, list[str]] = {
    "saludo": ["hola", "buenos dias", "buenas tardes", "buenas noches", "que puedes hacer", "quien eres",
               "ayuda", "como funcionas", "que sabes"],
    "importar": ["excel", "csv", "importar", "subir mis datos", "subir datos", "cargar datos", "plantilla",
                 "archivo", "como subo", "como cargo"],
    "impuestos": ["impuesto", "isr", "iva", "sat", "resico", "declaracion", "fiscal", "deducible", "deducir",
                  "regimen", "ptu"],
    "analisis_completo": ["analisis", "reporte", "estado financiero", "situacion", "diagnostico", "completo",
                          "como va mi negocio", "como esta mi negocio", "como voy", "resumen general", "panorama"],
    "ganancia": ["gane", "ganando", "ganancia", "utilidad", "rentab", "perdi", "perdiendo", "resultado",
                 "margen de mi negocio", "mi margen", "cuanto me queda"],
    "ventas": ["vendi", "venta", "ingreso", "facture", "cuanto entro"],
    "productos_top": ["producto", "deja mas", "mas rentable", "mejor producto", "top", "estrella", "mas vendido"],
    "productos_bajo": ["menos rentable", "peor producto", "margen bajo", "no me deja", "pierdo con", "deja menos",
                       "dejan menos", "menos me deja", "menor margen", "menos ganancia"],
    "inventario": ["inventario", "stock", "agot", "surtir", "resurtir", "pedido", "cuanto compro", "que compro",
                   "existencia", "reorden"],
    "gastos": ["gasto", "gaste", "gastando", "en que se va", "la renta", "sueldo", "nomina"],
    "flujo": ["efectivo", "alcanza", "alcanzar", "flujo", "caja", "liquidez", "dinero disponible", "cuanto dinero"],
    "equilibrio": ["equilibrio", "para no perder", "minimo que debo vender", "cuanto necesito vender", "cuanto debo vender"],
    "alertas": ["alerta", "aviso", "problema", "riesgo", "preocup", "atencion", "que hago"],
    "financiamiento": ["prestamo", "pedir credito", "un credito", "sacar credito", "financ", "invertir", "inversion"],
    "deudas": ["deuda", "debo", "tarjeta", "abono", "abonar", "liquidar", "intereses", "acreedor", "bola de nieve",
               "avalancha", "abalancha"],
    "comparar": ["compar", " vs ", "contra el", "respecto al", "frente al", "mes anterior", "mes pasado"],
    "pronostico": ["pronostic", "proyecc", "predic", "proximo mes", "voy a vender", "futuro", "esperar",
                   "siguiente mes", "voy a ganar", "estimacion"],
}

# "¿Qué productos van a mejorar su margen en 2 meses?" / "¿Qué productos se van a vender más?"
_FUTURO_PRODUCTO = re.compile(
    r"\b(mejorar\w*|empeor\w*|tendencia\w*|van a (subir|bajar|crecer|caer|vender)|se van a vender|venderan"
    r"|en \d+ meses|proximos? (\d+ )?meses)\b")

DESCRIPCIONES = {
    "saludo": "saludo o pregunta sobre qué puede hacer el asistente",
    "importar": "cómo subir o importar datos en Excel/CSV",
    "impuestos": "impuestos, ISR, IVA, SAT",
    "analisis_completo": "análisis financiero completo del negocio",
    "ganancia": "cuánto ganó o perdió, utilidad y margen",
    "ventas": "cuánto vendió",
    "productos_top": "qué productos dejan más ganancia",
    "productos_bajo": "qué productos dejan menos ganancia",
    "inventario": "inventario, stock, qué comprar",
    "gastos": "en qué gasta, distribución de gastos",
    "flujo": "efectivo disponible y si le va a alcanzar",
    "equilibrio": "cuánto necesita vender para no perder",
    "alertas": "problemas, riesgos y alertas del negocio",
    "financiamiento": "préstamos, créditos o financiamiento",
    "comparar": "comparar un periodo con otro",
    "pronostico": "proyección de ventas o efectivo a futuro",
    "deudas": "sus deudas actuales, cuánto debe, intereses, plan para pagarlas",
    "tendencia_productos": "qué productos van a mejorar o empeorar su margen o sus ventas en los próximos meses",
    "concepto": "que le expliquen qué significa un término financiero o cómo se calcula algo",
    "fuera_de_alcance": "algo que no tiene que ver con las finanzas, ventas, productos o gastos de su tienda",
}


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def intencion_por_reglas(mensaje: str) -> str | None:
    texto = f" {sin_acentos(mensaje)} "
    if "producto" in texto and _FUTURO_PRODUCTO.search(texto):
        return "tendencia_productos"
    # "¿Qué es el punto de equilibrio?" pide una explicación; "¿Cuál es mi punto de equilibrio?" pide la cifra.
    conceptos = glosario.buscar(texto)
    if conceptos and glosario.pide_explicacion(texto):
        return "concepto"
    puntajes = {nombre: sum(p in texto for p in patrones) for nombre, patrones in INTENCIONES.items()}
    # Las específicas ganan a las genéricas cuando ambas aparecen.
    if puntajes["productos_bajo"]:
        puntajes["productos_top"] = 0
    if puntajes["comparar"] and (puntajes["ventas"] or puntajes["ganancia"] or puntajes["gastos"]):
        puntajes["comparar"] += 1
    mejor = max(puntajes, key=lambda k: puntajes[k])
    if puntajes[mejor] > 0:
        return mejor
    return "concepto" if conceptos else None


def intencion_por_llm(mensaje: str) -> str | None:
    opciones = "\n".join(f"- {k}: {v}" for k, v in DESCRIPCIONES.items())
    crudo = get_llm().chat(
        "Clasifica la pregunta de un dueño de tienda en UNA intención. Responde solo JSON "
        '{"intencion": "<clave>"} usando una de estas claves:\n' + opciones,
        mensaje, formato_json=True, temperatura=0, max_tokens=30,
    )
    try:
        intencion = json.loads(crudo or "{}").get("intencion")
    except (json.JSONDecodeError, AttributeError):
        return None
    return intencion if intencion in DESCRIPCIONES else None


@dataclass
class PeriodoDetectado:
    desde: date
    hasta: date
    explicito: bool      # True si la pregunta mencionaba el periodo


def detectar_periodo(mensaje: str, corte: date, por_defecto: tuple[date, date] | None) -> PeriodoDetectado:
    """Interpreta 'agosto', 'agosto 2025', 'mes pasado', 'este año', 'últimos 3 meses'...

    `corte` es la fecha del último dato registrado: funciona como "hoy" del negocio.
    """
    texto = sin_acentos(mensaje)
    mes_corte = corte.replace(day=1)

    anio_txt = re.search(r"\b(20\d{2})\b", texto)
    anio = int(anio_txt.group(1)) if anio_txt else None

    for i, nombre in enumerate(MESES, start=1):
        if re.search(rf"\b{nombre}\b", texto):
            if anio is None:
                anio = corte.year if i <= corte.month else corte.year - 1
            inicio = date(anio, i, 1)
            return PeriodoDetectado(inicio, min(fin_de_mes(inicio), corte), True)

    if m := re.search(r"ultimos?\s+(\d+)\s+mes", texto):
        n = max(1, min(int(m.group(1)), 24))
        return PeriodoDetectado(sumar_meses(mes_corte, -(n - 1)), corte, True)
    if m := re.search(r"ultimos?\s+(\d+)\s+dia", texto):
        n = max(1, min(int(m.group(1)), 730))
        return PeriodoDetectado(corte - timedelta(days=n - 1), corte, True)
    if "mes pasado" in texto or "mes anterior" in texto:
        inicio = sumar_meses(mes_corte, -1)
        return PeriodoDetectado(inicio, fin_de_mes(inicio), True)
    if "este mes" in texto or "mes actual" in texto or "este ultimo mes" in texto:
        return PeriodoDetectado(mes_corte, corte, True)
    if "ano pasado" in texto or "ano anterior" in texto:
        a = corte.year - 1
        return PeriodoDetectado(date(a, 1, 1), date(a, 12, 31), True)
    if "este ano" in texto or "lo que va del ano" in texto or "ano actual" in texto:
        return PeriodoDetectado(date(corte.year, 1, 1), corte, True)
    if "trimestre" in texto:
        inicio = sumar_meses(mes_corte, -2)
        return PeriodoDetectado(inicio, corte, True)
    if "semana" in texto:
        return PeriodoDetectado(corte - timedelta(days=6), corte, True)
    if anio:
        return PeriodoDetectado(date(anio, 1, 1), min(date(anio, 12, 31), corte), True)
    if por_defecto:
        return PeriodoDetectado(por_defecto[0], por_defecto[1], False)
    return PeriodoDetectado(mes_corte, corte, False)
