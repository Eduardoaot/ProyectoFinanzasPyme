"""Fórmulas de proyecciones: equilibrio, inventario y reparto de la utilidad (funciones puras)."""

import math
from dataclasses import dataclass

Z_95 = 1.65                      # nivel de servicio de 95 %
DIAS_EXCESO = 60                 # más de 60 días de cobertura = inventario excesivo


def r2(valor: float) -> float:
    return round(valor + 0.0, 2)


# ------------------------------------------------------------------ punto de equilibrio


def punto_equilibrio_mensual(gastos_operacion_mensuales: float, margen_bruto: float | None) -> float | None:
    """Ventas al mes para cubrir los gastos: gastos de operación / margen bruto."""
    if margen_bruto is None or margen_bruto <= 0:
        return None
    return gastos_operacion_mensuales / margen_bruto


def margen_de_seguridad(ventas_proyectadas: float, punto_equilibrio: float | None) -> float | None:
    """(ventas proyectadas − punto de equilibrio) / ventas proyectadas."""
    if punto_equilibrio is None or ventas_proyectadas <= 0:
        return None
    return (ventas_proyectadas - punto_equilibrio) / ventas_proyectadas


# ------------------------------------------------------------------ inventario


def stock_seguridad(sigma_demanda: float, lead_time: float) -> float:
    """1.65 × σ_demanda × √lead_time (servicio de 95 %)."""
    return Z_95 * sigma_demanda * math.sqrt(lead_time)


def punto_reorden(demanda_diaria: float, lead_time: float, seguridad: float) -> float:
    return demanda_diaria * lead_time + seguridad


def dias_cobertura(existencias: float, demanda_diaria: float) -> float | None:
    if demanda_diaria <= 0:
        return None
    return existencias / demanda_diaria


def cantidad_sugerida(demanda_diaria: float, lead_time: float, periodo_revision: float, seguridad: float,
                      existencias: float, empaque: float = 1.0) -> float:
    """max(0, demanda × (lead_time + revisión) + seguridad − existencias), redondeada hacia arriba al empaque."""
    faltante = max(0.0, demanda_diaria * (lead_time + periodo_revision) + seguridad - existencias)
    if faltante <= 0:
        return 0.0
    paquete = empaque if empaque and empaque > 0 else 1.0
    return math.ceil(faltante / paquete - 1e-9) * paquete


def semaforo_reabasto(cobertura: float | None, existencias: float, lead_time: float, reorden: float) -> str:
    """Rojo: se acaba antes de que llegue el pedido · amarillo: ya toca pedir · verde: suficiente."""
    if cobertura is None:
        return "sin_movimiento"
    if cobertura < lead_time:
        return "rojo"
    if existencias < reorden:
        return "amarillo"
    return "verde"


def monto_detenido(existencias: float, demanda_diaria: float, costo: float, dias_max: int = DIAS_EXCESO) -> float:
    """Dinero en piezas que exceden 60 días de venta."""
    exceso = existencias - demanda_diaria * dias_max
    return max(0.0, exceso) * costo


@dataclass
class CompraCandidata:
    id_producto: int
    costo: float
    contribucion: float          # (precio − costo) × demanda diaria: ganancia diaria que genera el producto
    cantidad: float


def priorizar_compras(candidatas: list[CompraCandidata], presupuesto: float) -> tuple[list[int], list[int]]:
    """Compra primero lo que más ganancia genera. Devuelve (ids a comprar, ids a posponer)."""
    comprar, posponer, restante = [], [], max(0.0, presupuesto)
    for c in sorted(candidatas, key=lambda c: (-c.contribucion, c.id_producto)):
        if c.cantidad <= 0:
            continue
        if c.costo <= restante + 1e-9:
            comprar.append(c.id_producto)
            restante -= c.costo
        else:
            posponer.append(c.id_producto)
    return comprar, posponer


# ------------------------------------------------------------------ efectivo y ahorro


def dias_de_colchon(efectivo: float, gasto_diario: float) -> float | None:
    if gasto_diario <= 0:
        return None
    return max(0.0, efectivo) / gasto_diario


def meta_fondo_emergencia(gastos_fijos_mensuales: float, pagos_deuda_mensuales: float) -> float:
    """3 meses de gastos fijos + pagos de deuda."""
    return 3 * (gastos_fijos_mensuales + pagos_deuda_mensuales)


def distribuir_utilidad(utilidad: float, impuestos: float, deuda_obligatoria: float, deuda_extra: float,
                        fondo: float, reinversion: float) -> dict:
    """Reparte la utilidad proyectada en orden de prioridad; lo que sobra es el retiro del dueño.

    Prioridad: 1) impuestos · 2) deuda (obligatoria + extra) · 3) fondo de emergencia · 4) reinversión · 5) retiro.
    Si no alcanza para 1 y 2 devuelve el faltante exacto.
    """
    restante = max(0.0, utilidad)
    partes = []
    for clave, deseado in (("impuestos", impuestos), ("deuda_obligatoria", deuda_obligatoria), ("deuda_extra", deuda_extra),
                           ("fondo_emergencia", fondo), ("reinversion", reinversion)):
        asignado = min(restante, max(0.0, deseado))
        partes.append({"clave": clave, "deseado": r2(deseado), "asignado": r2(asignado)})
        restante -= asignado
    partes.append({"clave": "retiro", "deseado": r2(restante), "asignado": r2(restante)})
    obligatorio = max(0.0, impuestos) + max(0.0, deuda_obligatoria)
    return {"partes": partes, "faltante_obligatorio": r2(max(0.0, obligatorio - max(0.0, utilidad)))}
