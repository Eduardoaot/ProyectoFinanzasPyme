"""Pronóstico de ventas diarias (determinista, sin LLM ni aleatoriedad).

Método:
  1. venta_base_diaria = promedio de las últimas 8 semanas (56 días).
  2. índice del día de la semana = promedio de ese día / promedio diario (últimas 12 semanas).
  3. tendencia = pendiente (mínimos cuadrados) de las ventas semanales de las últimas 12 semanas,
     limitada a ±15 % de la venta base para no extrapolar crecimientos extremos.
  4. pronóstico_día = (venta_base + tendencia_diaria × t) × índice_día.
El rango (pesimista / optimista) sale de la desviación estándar de los errores del método
en las últimas 8 semanas (backtest): ±1.28 σ (nivel de confianza de 80 %).
"""

import statistics
from dataclasses import dataclass
from datetime import date, timedelta

SEMANAS_BASE = 8
SEMANAS_INDICE = 12
SEMANAS_BACKTEST = 8
LIMITE_TENDENCIA = 0.15
Z_80 = 1.28


@dataclass(frozen=True)
class Ajuste:
    base: float
    indices: tuple[float, ...]       # lunes..domingo
    tendencia_diaria: float          # cambio del nivel diario por cada día transcurrido


@dataclass(frozen=True)
class ResultadoPronostico:
    fechas: list[date]
    valores: list[float]
    sigma_diaria: float
    precision: float | None          # 100 − MAPE semanal, en % (None si no hay backtest)
    pocos_datos: bool
    base: float
    tendencia_diaria: float
    indices: tuple[float, ...]
    metodo: str


def _pendiente(y: list[float]) -> float:
    """Pendiente de la regresión lineal por mínimos cuadrados de y contra 0..n-1."""
    n = len(y)
    if n < 2:
        return 0.0
    x_med, y_med = (n - 1) / 2, sum(y) / n
    den = sum((i - x_med) ** 2 for i in range(n))
    return sum((i - x_med) * (v - y_med) for i, v in enumerate(y)) / den


def ajustar(historico: list[tuple[date, float]]) -> Ajuste:
    """Calcula base, índices semanales y tendencia con el historial disponible (≥ 8 semanas)."""
    valores = [v for _, v in historico]
    base = statistics.fmean(valores[-7 * SEMANAS_BASE:])
    ventana = historico[-7 * SEMANAS_INDICE:]
    promedio = statistics.fmean(v for _, v in ventana)
    indices = []
    for dia in range(7):
        del_dia = [v for f, v in ventana if f.weekday() == dia]
        indices.append(statistics.fmean(del_dia) / promedio if del_dia and promedio > 0 else 1.0)
    semanas = [sum(valores[len(valores) - 7 * (k + 1): len(valores) - 7 * k]) for k in range(SEMANAS_INDICE - 1, -1, -1)
               if len(valores) >= 7 * (k + 1)]
    pendiente_semanal = _pendiente(semanas)
    return Ajuste(base, tuple(indices), pendiente_semanal / 49)   # nivel diario cambia b/7 por semana = b/49 por día


def _proyectar(a: Ajuste, ultima: date, horizonte: int) -> tuple[list[date], list[float]]:
    tope = LIMITE_TENDENCIA * a.base
    fechas, valores = [], []
    for t in range(1, horizonte + 1):
        f = ultima + timedelta(days=t)
        ajuste_tendencia = max(-tope, min(tope, a.tendencia_diaria * t))
        fechas.append(f)
        valores.append(max(0.0, (a.base + ajuste_tendencia) * a.indices[f.weekday()]))
    return fechas, valores


def _backtest(historico: list[tuple[date, float]]) -> tuple[list[float], list[float]]:
    """Errores diarios (real − pronóstico) y errores porcentuales semanales de las últimas 8 semanas."""
    errores, mape = [], []
    n = len(historico)
    for w in range(SEMANAS_BACKTEST, 0, -1):
        corte = n - 7 * w
        if corte < 7 * SEMANAS_BASE:
            continue
        entrenamiento = historico[:corte]
        _, previsto = _proyectar(ajustar(entrenamiento), entrenamiento[-1][0], 7)
        real = [v for _, v in historico[corte:corte + 7]]
        errores.extend(r - p for r, p in zip(real, previsto))
        if sum(real) > 0:
            mape.append(abs(sum(real) - sum(previsto)) / sum(real))
    return errores, mape


def pronosticar(historico: list[tuple[date, float]], horizonte: int) -> ResultadoPronostico:
    """`historico`: serie diaria continua (con ceros en días sin venta) que termina en el día de corte."""
    if not historico:
        return ResultadoPronostico([], [], 0.0, None, True, 0.0, 0.0, (1.0,) * 7, "sin_datos")
    ultima = historico[-1][0]
    valores = [v for _, v in historico]
    if len(historico) < 7 * SEMANAS_BASE:
        promedio = statistics.fmean(valores)
        sigma = statistics.pstdev(valores) if len(valores) > 1 else 0.0
        fechas = [ultima + timedelta(days=t) for t in range(1, horizonte + 1)]
        return ResultadoPronostico(fechas, [promedio] * horizonte, sigma, None, True, promedio, 0.0, (1.0,) * 7,
                                   "promedio_simple")
    ajuste = ajustar(historico)
    fechas, previstos = _proyectar(ajuste, ultima, horizonte)
    errores, mape = _backtest(historico)
    if len(errores) > 1:
        sigma = statistics.pstdev(errores)
    else:
        sigma = statistics.pstdev(valores[-7 * SEMANAS_BASE:])
    precision = max(0.0, 100 * (1 - statistics.fmean(mape))) if mape else None
    return ResultadoPronostico(fechas, previstos, sigma, precision, False, ajuste.base, ajuste.tendencia_diaria,
                               ajuste.indices, "base_indice_tendencia")


def rango_acumulado(sigma_diaria: float, dias: int) -> float:
    """Ancho (±) del pronóstico acumulado de `dias` días: 1.28 · σ · √días."""
    return Z_80 * sigma_diaria * dias ** 0.5
