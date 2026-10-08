"""Fórmulas de ISR, IVA y PTU (funciones puras). Las tasas y tarifas vienen de parametros_fiscales.json."""

from dataclasses import dataclass

REGIMENES = {
    "626": "RESICO (persona física)",
    "612": "Actividades Empresariales (persona física)",
    "601": "General de Ley (persona moral)",
}


def r2(valor: float) -> float:
    return round(valor + 0.0, 2)


def codigo_regimen(regimen_fiscal: str | None, tipo_persona: str = "fisica") -> str:
    """Convierte el texto guardado en la empresa ('RESICO', 'Persona Física con Actividad Empresarial'…) a clave SAT."""
    if tipo_persona == "moral":
        return "601"
    texto = (regimen_fiscal or "").lower()
    if texto.strip() in ("626", "612", "601"):
        return texto.strip()
    if "resico" in texto or "confianza" in texto:
        return "626"
    if "general" in texto and "ley" in texto:
        return "601"
    return "612" if texto else "626"


# ------------------------------------------------------------------ IVA


def base_sin_iva(precio_con_iva: float, tasa: float) -> float:
    """Los precios incluyen IVA: base = precio / (1 + tasa)."""
    return precio_con_iva / (1 + tasa)


def iva_incluido(precio_con_iva: float, tasa: float) -> float:
    return precio_con_iva - base_sin_iva(precio_con_iva, tasa)


def iva_a_pagar(trasladado: float, acreditable: float, retenciones: float = 0.0, saldo_favor_previo: float = 0.0) -> dict:
    """IVA del mes = trasladado − acreditable − retenciones. Si es negativo hay saldo a favor,
    que se acredita contra los meses siguientes."""
    neto = trasladado - acreditable - retenciones - saldo_favor_previo
    return {"neto": neto, "a_pagar": max(0.0, neto), "saldo_a_favor": max(0.0, -neto)}


# ------------------------------------------------------------------ ISR


def tasa_resico(ingresos_mes: float, tabla: list[dict]) -> float:
    """Tasa mensual de RESICO según el ingreso del mes (art. 113-E LISR)."""
    for tramo in tabla:
        if ingresos_mes <= tramo["hasta"]:
            return tramo["tasa"]
    return tabla[-1]["tasa"]


def isr_resico(ingresos_mes: float, tabla: list[dict], retenciones: float = 0.0) -> dict:
    """RESICO: ingresos cobrados del mes × tasa − retenciones. No hay deducciones."""
    tasa = tasa_resico(ingresos_mes, tabla)
    bruto = ingresos_mes * tasa
    return {"tasa": tasa, "isr_causado": bruto, "isr_a_pagar": max(0.0, bruto - retenciones)}


def isr_tarifa(base: float, tarifa_mensual: list[dict], meses: int = 1) -> float:
    """Tarifa del art. 96 LISR acumulada: límites y cuota fija de la tarifa mensual × número de meses.

    ISR = (base − límite inferior) × % sobre el excedente + cuota fija.
    """
    if base <= 0:
        return 0.0
    escogido = tarifa_mensual[0]
    for tramo in tarifa_mensual:
        if base >= tramo["limite_inferior"] * meses:
            escogido = tramo
    return (base - escogido["limite_inferior"] * meses) * escogido["tasa"] + escogido["cuota_fija"] * meses


def tasa_marginal(base: float, tarifa_mensual: list[dict], meses: int = 1) -> float:
    escogido = tarifa_mensual[0]
    for tramo in tarifa_mensual:
        if base >= tramo["limite_inferior"] * meses:
            escogido = tramo
    return escogido["tasa"]


def pago_provisional_612(ingresos_acum: float, deducciones_acum: float, ptu_pagada: float, perdidas: float,
                         tarifa_mensual: list[dict], meses: int, pagos_previos: float, retenciones: float = 0.0) -> dict:
    """Actividades empresariales: ISR acumulado del año menos lo ya pagado en meses anteriores."""
    base = max(0.0, ingresos_acum - deducciones_acum - ptu_pagada - perdidas)
    isr_acum = isr_tarifa(base, tarifa_mensual, meses)
    pago = max(0.0, isr_acum - pagos_previos - retenciones)
    return {"base": base, "isr_acumulado": isr_acum, "pago_provisional": pago}


def pago_provisional_601(ingresos_acum: float, coeficiente: float, tasa: float, pagos_previos: float) -> dict:
    """Persona moral: utilidad fiscal estimada = ingresos acumulados × coeficiente de utilidad; ISR al 30 %."""
    utilidad = ingresos_acum * coeficiente
    isr_acum = utilidad * tasa
    return {"base": utilidad, "isr_acumulado": isr_acum, "pago_provisional": max(0.0, isr_acum - pagos_previos)}


def ptu(renta_gravable_anual: float, porcentaje: float) -> float:
    """10 % de la renta gravable anual (base de PTU)."""
    return max(0.0, renta_gravable_anual) * porcentaje


def limite_resico_alcanzado(ingresos_acumulados: float, limite: float, aviso: float) -> str:
    """'ok', 'cerca' (≥ 85 % del límite) o 'excedido'."""
    if ingresos_acumulados > limite:
        return "excedido"
    return "cerca" if ingresos_acumulados >= limite * aviso else "ok"


@dataclass(frozen=True)
class DepreciacionAnual:
    tasa: float
    monto_deducible_anual: float


def depreciacion(valor: float, clase: str, parametros_dep: dict) -> DepreciacionAnual:
    """Deducción anual por inversión: mobiliario 10 %, cómputo 30 %, autos 25 % con tope de $175,000."""
    tasa = parametros_dep[clase]
    base = min(valor, parametros_dep["tope_auto"]) if clase == "autos" else valor
    return DepreciacionAnual(tasa, r2(base * tasa))
