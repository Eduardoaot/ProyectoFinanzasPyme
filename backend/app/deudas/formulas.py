"""Fórmulas de deudas (funciones puras, sin base de datos).

Las tasas se manejan como fracción anual (0.54 = 54 %). El IVA (16 %) se cobra sobre los
intereses cuando `aplica_iva` es verdadero. Todo es determinista; el redondeo a centavos
se hace al final, nunca en pasos intermedios.
"""

import math
from dataclasses import dataclass, field, replace
from typing import Literal

IVA = 0.16
MAX_MESES = 360
Estrategia = Literal["actual", "avalancha", "bola_de_nieve"]
TIPOS_REVOLVENTES = ("tarjeta_credito", "credito_revolvente")


def r2(valor: float) -> float:
    return round(valor + 0.0, 2)


def interes_mes(saldo: float, tasa_anual: float) -> float:
    """Interés ordinario del mes sobre saldos insolutos: saldo × (tasa anual / 12)."""
    return saldo * tasa_anual / 12


def iva_interes(interes: float, aplica_iva: bool) -> float:
    return interes * IVA if aplica_iva else 0.0


def pago_fijo(principal: float, tasa_anual: float, n_meses: int) -> float:
    """Amortización francesa: PMT = P·i / (1 − (1 + i)^−n). Sin IVA."""
    if n_meses <= 0:
        return principal
    i = tasa_anual / 12
    if i == 0:
        return principal / n_meses
    return principal * i / (1 - (1 + i) ** -n_meses)


@dataclass(frozen=True)
class FilaAmortizacion:
    mes: int
    interes: float
    iva: float
    capital: float
    pago: float
    saldo: float


def tabla_amortizacion(principal: float, tasa_anual: float, n_meses: int, aplica_iva: bool = False) -> list[FilaAmortizacion]:
    """Cuota fija de capital + interés; el IVA de los intereses se cobra aparte (así lo hacen los bancos)."""
    cuota = pago_fijo(principal, tasa_anual, n_meses)
    saldo, filas = principal, []
    for mes in range(1, n_meses + 1):
        interes = interes_mes(saldo, tasa_anual)
        iva = iva_interes(interes, aplica_iva)
        capital = min(saldo, cuota - interes)
        saldo = max(0.0, saldo - capital)
        filas.append(FilaAmortizacion(mes, r2(interes), r2(iva), r2(capital), r2(capital + interes + iva), r2(saldo)))
    return filas


def tasa_efectiva_mensual(tasa_anual: float, aplica_iva: bool) -> float:
    """Costo mensual del saldo: interés + IVA del interés."""
    return tasa_anual / 12 * (1 + (IVA if aplica_iva else 0.0))


def nunca_baja(saldo: float, tasa_anual: float, pago: float, aplica_iva: bool = False) -> bool:
    """Con este pago la deuda no disminuye: el pago no cubre ni los intereses (con IVA)."""
    return saldo > 0 and pago <= saldo * tasa_efectiva_mensual(tasa_anual, aplica_iva) + 1e-9


def meses_para_liquidar(saldo: float, tasa_anual: float, pago: float, aplica_iva: bool = False) -> float | None:
    """n = −ln(1 − i·P/A) / ln(1 + i). None si el pago no alcanza para bajar la deuda."""
    if saldo <= 0:
        return 0.0
    if nunca_baja(saldo, tasa_anual, pago, aplica_iva):
        return None
    i = tasa_efectiva_mensual(tasa_anual, aplica_iva)
    if i == 0:
        return saldo / pago
    return -math.log(1 - i * saldo / pago) / math.log(1 + i)


def pago_minimo_tarjeta(saldo: float, limite: float | None, tasa_anual: float, aplica_iva: bool = True) -> float:
    """Criterio Banxico: el mayor entre 1.5 % del saldo + intereses + IVA y 1.25 % del límite de crédito."""
    interes = interes_mes(saldo, tasa_anual)
    con_iva = interes + iva_interes(interes, aplica_iva)
    a = 0.015 * saldo + con_iva
    b = 0.0125 * (limite or 0.0)
    return r2(min(max(a, b), saldo + con_iva))


def utilizacion(saldo: float, limite: float | None) -> float | None:
    if not limite:
        return None
    return saldo / limite


# --------------------------------------------------------------------------- simulación


@dataclass
class DeudaSim:
    """Datos mínimos de una deuda para simular su pago mes a mes."""

    id: int
    acreedor: str
    tipo: str
    saldo: float
    tasa_anual: float
    aplica_iva: bool = False
    pago: float | None = None           # pago mensual programado total; None = se calcula
    limite: float | None = None
    comision: float = 0.0
    meses_restantes: int | None = None


def pago_programado(d: DeudaSim, saldo: float) -> float:
    """Pago del mes que exige el acreedor (sin extras)."""
    if d.tipo in TIPOS_REVOLVENTES:
        return pago_minimo_tarjeta(saldo, d.limite, d.tasa_anual, d.aplica_iva)
    if d.pago is not None:
        return d.pago
    i = tasa_efectiva_mensual(d.tasa_anual, d.aplica_iva)
    if d.tipo == "proveedor":
        return saldo * (1 + i)
    n = max(1, d.meses_restantes or 1)
    return saldo / n if i == 0 else saldo * i / (1 - (1 + i) ** -n)


@dataclass
class MesSim:
    mes: int
    saldo_total: float
    capital: float
    interes: float               # intereses + IVA + comisiones
    pago_total: float
    pagos: dict[int, float] = field(default_factory=dict)


@dataclass
class ResultadoSim:
    estrategia: str
    meses: list[MesSim]
    liquidacion: dict[int, int | None]     # id_deuda → mes en que termina (None = no termina)
    orden: list[int]                       # orden en que se terminan las deudas
    interes_total: float
    meses_totales: int | None              # None si alguna deuda nunca se liquida


def simular(deudas: list[DeudaSim], estrategia: Estrategia = "actual", extra_mensual: float = 0.0,
            max_meses: int = MAX_MESES) -> ResultadoSim:
    """Simula el pago de todas las deudas.

    - "actual": cada deuda paga solo lo programado (sin extra ni reutilizar lo que se libera).
    - "avalancha" / "bola_de_nieve": el monto mensual total se mantiene fijo (pagos programados del
      primer mes + extra); lo que se libera al terminar una deuda se suma al extra. Avalancha lo manda
      a la deuda con la tasa más alta; bola de nieve, a la de saldo más pequeño.
    """
    saldos = {d.id: d.saldo for d in deudas if d.saldo > 0}
    por_id = {d.id: d for d in deudas}
    liquidacion: dict[int, int | None] = {d.id: (0 if d.saldo <= 0 else None) for d in deudas}
    presupuesto = sum(pago_programado(por_id[i], s) for i, s in saldos.items()) + max(0.0, extra_mensual)
    filas: list[MesSim] = []
    interes_total, orden = 0.0, []

    for mes in range(1, max_meses + 1):
        if not saldos:
            break
        cargos: dict[int, tuple[float, float, float]] = {}   # id → (interés, iva, comisión)
        pagos: dict[int, float] = {}
        for i, s in saldos.items():
            d = por_id[i]
            it = interes_mes(s, d.tasa_anual)
            cargos[i] = (it, iva_interes(it, d.aplica_iva), d.comision)
            pagos[i] = min(pago_programado(d, s), s + it + cargos[i][1])
        if estrategia != "actual":
            sobrante = presupuesto - sum(pagos.values())
            if estrategia == "avalancha":
                prioridad = sorted(saldos, key=lambda i: (-por_id[i].tasa_anual, saldos[i]))
            else:
                prioridad = sorted(saldos, key=lambda i: (saldos[i], -por_id[i].tasa_anual))
            for i in prioridad:
                if sobrante <= 0.005:
                    break
                it, iva, _ = cargos[i]
                abono = min(sobrante, max(0.0, saldos[i] + it + iva - pagos[i]))
                pagos[i] += abono
                sobrante -= abono
        capital_mes = costo_mes = pago_mes = 0.0
        for i in list(saldos):
            it, iva, com = cargos[i]
            saldos[i] = max(0.0, saldos[i] - (pagos[i] - it - iva))
            capital_mes += pagos[i] - it - iva
            costo_mes += it + iva + com
            pago_mes += pagos[i] + com
            if saldos[i] <= 0.005:
                del saldos[i]
                liquidacion[i] = mes
                orden.append(i)
        interes_total += costo_mes
        filas.append(MesSim(mes, r2(sum(saldos.values())), r2(capital_mes), r2(costo_mes), r2(pago_mes),
                            {k: r2(v) for k, v in pagos.items()}))

    return ResultadoSim(estrategia, filas, liquidacion, orden, r2(interes_total), None if saldos else len(filas))


def ahorro_pago_extra(deuda: DeudaSim, extra_mensual: float) -> dict:
    """Compara una deuda con su pago normal contra el mismo pago + un abono extra cada mes."""
    base = simular([deuda], "actual")
    pago = pago_programado(deuda, deuda.saldo) + extra_mensual
    con_extra = simular([replace(deuda, pago=pago, tipo="credito_simple" if deuda.tipo in TIPOS_REVOLVENTES else deuda.tipo)])
    ambos = base.meses_totales is not None and con_extra.meses_totales is not None
    return {
        "interes_sin_extra": base.interes_total, "meses_sin_extra": base.meses_totales,
        "interes_con_extra": con_extra.interes_total, "meses_con_extra": con_extra.meses_totales,
        "ahorro_interes": r2(base.interes_total - con_extra.interes_total),
        "meses_ahorrados": base.meses_totales - con_extra.meses_totales if ambos else None,
    }


def tasa_promedio_ponderada(saldos_tasas: list[tuple[float, float]]) -> float | None:
    """Σ(saldo × tasa) / Σ saldo."""
    total = sum(s for s, _ in saldos_tasas)
    if total <= 0:
        return None
    return sum(s * t for s, t in saldos_tasas) / total


def dscr(utilidad_operativa_mensual: float, pago_mensual_total: float) -> float | None:
    """Cobertura del servicio de deuda: ≥ 1.25 sano · 1.0–1.25 justo · < 1.0 no alcanza."""
    if pago_mensual_total <= 0:
        return None
    return utilidad_operativa_mensual / pago_mensual_total


def semaforo_dscr(valor: float | None) -> str:
    if valor is None:
        return "verde"
    return "verde" if valor >= 1.25 else "amarillo" if valor >= 1.0 else "rojo"


def semaforo_peso_deuda(fraccion_ventas: float | None) -> str:
    """< 15 % de tus ventas verde · 15–30 % amarillo · > 30 % rojo."""
    if fraccion_ventas is None or fraccion_ventas < 0.15:
        return "verde"
    return "amarillo" if fraccion_ventas <= 0.30 else "rojo"


def capacidad_endeudamiento(utilidad_operativa_mensual: float, pagos_actuales: float, tasa_anual: float,
                            plazo_meses: int = 12) -> dict:
    """Pago mensual máximo recomendado = utilidad / 1.25 − pagos actuales; y el crédito que ese pago permite."""
    maximo = max(0.0, utilidad_operativa_mensual / 1.25 - pagos_actuales)
    i = tasa_anual / 12
    monto = maximo * plazo_meses if i == 0 else maximo * (1 - (1 + i) ** -plazo_meses) / i
    return {"pago_maximo": r2(maximo), "monto_equivalente": r2(monto), "plazo_meses": plazo_meses}
