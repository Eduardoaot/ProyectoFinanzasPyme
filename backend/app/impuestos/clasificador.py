"""Clasificador de deducciones: "¿Esto se puede deducir?" (reglas deterministas, muestran el motivo)."""

from dataclasses import dataclass

from app.impuestos.parametros import sin_acentos

SIN_IVA = ("sueldo", "nomina", "salario", "merma", "imss", "impuesto", "recargo", "multa")
NO_DEDUCIBLES = (
    (("multa", "recargo", "actualizacion", "infraccion"), "Las multas, recargos y actualizaciones nunca se deducen."),
    (("isr ", "impuesto sobre la renta", "iva no acreditable", "pago de iva", "pago de isr"),
     "El propio ISR y el IVA no acreditable no son deducibles."),
    (("regalo", "obsequio"), "Los regalos y obsequios no relacionados con la venta no se deducen."),
)
RESTAURANTE = ("restaurante", "comida", "consumo", "alimentos del personal", "cafeteria")
RENTA_AUTO = ("renta de auto", "renta de automovil", "arrendamiento de auto")
PRESTACIONES = ("vales de despensa", "fondo de ahorro", "prestacion", "aguinaldo", "vacaciones")
COMBUSTIBLE = ("gasolina", "diesel", "combustible")


@dataclass(frozen=True)
class Clasificacion:
    estado: str                    # deducible | parcial | no_deducible
    porcentaje: float              # fracción deducible (0–1)
    monto_deducible: float
    motivo: str
    acredita_iva: bool             # ¿el IVA de este gasto se puede acreditar?
    perdido_por: str | None = None  # 'sin_cfdi' | 'efectivo' | None: causas que el dueño sí puede corregir


def _contiene(texto: str, claves: tuple[str, ...]) -> bool:
    return any(c in texto for c in claves)


def tasa_iva_gasto(concepto: str, categoria: str) -> float:
    """Los sueldos, mermas e impuestos no llevan IVA; lo demás, 16 %."""
    texto = sin_acentos(f"{concepto} {categoria}")
    return 0.0 if _contiene(texto, SIN_IVA) else 0.16


def clasificar(concepto: str, categoria: str, monto: float, tiene_cfdi: bool, medio_pago: str, uso: str,
               regimen: str, limite_efectivo: float = 2000.0, ded: dict | None = None) -> Clasificacion:
    ded = ded or {"restaurantes": 0.085, "renta_auto_diario": 200.0, "prestaciones_exentas": 0.47}
    texto = sin_acentos(f"{concepto} {categoria}")
    en_efectivo = medio_pago == "efectivo"

    if uso == "personal":
        return Clasificacion("no_deducible", 0.0, 0.0, "Es un gasto personal o familiar, no del negocio.", False)
    for claves, motivo in NO_DEDUCIBLES:
        if _contiene(texto, claves):
            return Clasificacion("no_deducible", 0.0, 0.0, motivo, False)

    # Causas corregibles: sin factura o efectivo mayor a $2,000 (afectan ISR en 612/601 y siempre el IVA).
    perdido = None
    if not tiene_cfdi:
        perdido, motivo = "sin_cfdi", "No tienes la factura (CFDI) a nombre de tu negocio. Pídela siempre."
    elif en_efectivo and monto > limite_efectivo:
        perdido, motivo = "efectivo", f"Pagos en efectivo mayores a ${limite_efectivo:,.0f} no se deducen. Paga con transferencia o tarjeta."
    elif en_efectivo and _contiene(texto, COMBUSTIBLE):
        perdido, motivo = "efectivo", "La gasolina solo se deduce si se paga con tarjeta, transferencia o cheque."
    if perdido:
        return Clasificacion("no_deducible", 0.0, 0.0, motivo, False, perdido)

    if regimen == "626":
        return Clasificacion("no_deducible", 0.0, 0.0,
                             "En RESICO los gastos no se restan para el ISR, pero su IVA sí se puede acreditar.", True)
    if _contiene(texto, RESTAURANTE):
        p = ded["restaurantes"]
        return Clasificacion("parcial", p, round(monto * p, 2), f"Los consumos en restaurantes solo se deducen al {p * 100:.1f} %.", True)
    if _contiene(texto, RENTA_AUTO):
        tope = ded["renta_auto_diario"]
        return Clasificacion("parcial", min(1.0, tope / monto) if monto else 0.0, round(min(monto, tope), 2),
                             f"La renta de autos se deduce hasta ${tope:,.0f} por día.", True)
    if _contiene(texto, PRESTACIONES):
        p = ded["prestaciones_exentas"]
        return Clasificacion("parcial", p, round(monto * p, 2), f"Las prestaciones exentas se deducen al {p * 100:.0f} % (o 53 % según el caso).", False)
    return Clasificacion("deducible", 1.0, round(monto, 2), "Gasto del negocio con factura y bien pagado: se puede deducir.", True)
