"""Inicio sencillo: lo mínimo que necesita saber la dueña de una tienda muy pequeña, en una sola llamada.

No calcula nada nuevo: toma las cifras de los servicios que ya alimentan el modo avanzado (resumen,
productos, proyecciones, impuestos y deudas) y las reduce a pocas cosas fáciles de leer. Las frases
también las arma el código; el LLM solo entra cuando la persona le pregunta algo a Clara.
"""

import math
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import Connection

from app.alerts.reglas import umbrales_empresa
from app.config import UmbralesAlerta
from app.deudas import servicio as deudas_srv
from app.finance import consultas as q
from app.finance import servicio as fin
from app.finance.formato import dinero, numero, unidades
from app.finance.periodos import MESES, fin_de_mes, sumar_meses
from app.impuestos import servicio as imp_srv
from app.proyecciones import servicio as proy_srv

Estado = Literal["verde", "amarillo", "rojo"]
MESES_GRAFICA = 6
MAX_PRODUCTOS = 8
MAX_COMPRAS = 5
DIAS_A_CUBRIR = 14                    # la sugerencia de compra alcanza para 2 semanas (igual que en Productos)


class ComoTeFue(BaseModel):
    mes: str                          # "septiembre" o "lo que va de octubre"
    ventas: float
    te_quedo: float                   # utilidad: ventas − mercancía − gastos
    gastaste: float                   # mercancía vendida + gastos del negocio
    cambio_ventas: float | None       # vs el periodo anterior (fracción)
    estado: Estado
    frase: str


class MesVentas(BaseModel):
    etiqueta: str
    ventas: float
    actual: bool


class ProductoSencillo(BaseModel):
    nombre: str
    unidad: str
    vendiste: float                   # unidades del mes
    te_dejo: float                    # utilidad del mes
    inventario: Literal["verde", "amarillo", "rojo", "sin_movimiento"]
    precio: float                     # precio de venta actual
    costo: float                      # costo promedio actual
    te_quedan: float                  # existencia hoy
    dias_te_alcanzan: float | None    # días de inventario al ritmo de venta actual
    pide: float                       # piezas sugeridas para cubrir DIAS_A_CUBRIR (0 = no hace falta)
    consejo: str                      # una línea: qué hacer con este producto
    consejo_estado: Estado            # color del consejo (rojo: actúa ya, amarillo: atención, verde: va bien)


class Compra(BaseModel):
    nombre: str
    cantidad: float
    unidad: str
    costo: float


class LoQueViene(BaseModel):
    mes: str
    ventas_esperadas: float
    ganancia_esperada: float
    efectivo_hoy: float
    efectivo_fin_de_mes: float
    te_alcanza: bool
    fecha_riesgo: str | None
    comprar: list[Compra]
    total_compra: float


class HastaLaAnual(BaseModel):
    fecha_anual: str                  # día límite de la declaración anual (30 de abril para personas físicas)
    pagos_mensuales: int              # cuántos pagos mensuales vencen antes (incluido el del mes)
    total_mensuales: float
    ajuste_anual: float | None        # lo que quedaría en la anual; None si no se puede estimar
    total: float                      # todo lo que pagarías desde hoy hasta la anual (aproximado)


class ImpuestosSencillo(BaseModel):
    mes: str
    a_pagar: float
    fecha_limite: str
    saldo_a_favor: float
    regimen: str
    periodo_desde: str                # días que cubre el pago del mes
    periodo_hasta: str
    hasta_la_anual: HastaLaAnual


class DeudasSencillo(BaseModel):
    total: float
    pago_del_mes: float
    paga_primero: str | None
    proximo_pago: dict | None         # {"acreedor", "fecha", "monto"}


class Inicio(BaseModel):
    tiene_datos: bool
    como_te_fue: ComoTeFue | None = None
    ventas_por_mes: list[MesVentas] = []
    productos: list[ProductoSencillo] = []
    lo_que_viene: LoQueViene | None = None
    impuestos: ImpuestosSencillo | None = None
    deudas: DeudasSencillo | None = None


def estado_del_mes(ventas: float, utilidad: float, cambio_ventas: float | None, mes: str,
                   u: UmbralesAlerta) -> tuple[Estado, str]:
    """Semáforo y frase de "¿Cómo te fue?" con los mismos umbrales que las alertas."""
    if utilidad < 0:
        return "rojo", f"En {mes} gastaste más de lo que vendiste: perdiste {dinero(round(-utilidad))}."
    margen = utilidad / ventas if ventas else 0.0
    if cambio_ventas is not None and cambio_ventas <= -u.caida_ventas:
        return "amarillo", (f"En {mes} sí te quedaron {dinero(round(utilidad))}, pero vendiste menos que el mes anterior. "
                            "Vale la pena ver por qué.")
    if margen < u.margen_neto_bajo:
        return "amarillo", (f"En {mes} te quedaron {dinero(round(utilidad))} de {dinero(round(ventas))} que vendiste. "
                            "Ganas, pero poco: revisa tus gastos y tus precios.")
    return "verde", f"En {mes} te fue bien: vendiste {dinero(round(ventas))} y te quedaron {dinero(round(utilidad))}."


def cantidad_a_pedir(venta_diaria: float, existencia: float, dias: int = DIAS_A_CUBRIR) -> float:
    """Piezas que faltan para cubrir `dias` al ritmo actual (redondeado hacia arriba, nunca negativo)."""
    return float(max(0, math.ceil(venta_diaria * dias - existencia)))


def consejo_producto(precio: float, costo: float, venta_diaria: float, dias_te_alcanzan: float | None,
                     semaforo: str, pide: float, unidad: str, u: UmbralesAlerta) -> tuple[Estado, str]:
    """Una sola línea, directa, con las cifras ya calculadas. Prioridad: se acaba > deja poco > no se vende > va bien."""
    margen = (precio - costo) / precio if precio else None
    if semaforo in ("rojo", "amarillo") and pide > 0:
        urge = semaforo == "rojo"
        return ("rojo" if urge else "amarillo"), (f"{'Se te acaba' if urge else 'Pide pronto'}: pide unas "
                                                  f"{unidades(pide, unidad)} para {DIAS_A_CUBRIR // 7} semanas.")
    if margen is not None and margen < u.margen_producto_bajo:
        return "amarillo", f"Te deja poco: {dinero(round(precio - costo, 2))} por {unidad}. Revisa su precio o su costo."
    if venta_diaria <= 0:
        return "amarillo", "Este mes no se vendió. No pidas más por ahora."
    if dias_te_alcanzan is not None:
        return "verde", f"Vas bien: te alcanza para unos {numero(round(dias_te_alcanzan))} días."
    return "verde", "Vas bien."


def _nombre_mes(desde: date, hasta: date) -> str:
    nombre = MESES[desde.month - 1]
    return nombre if hasta == fin_de_mes(hasta) else f"lo que va de {nombre}"


def inicio(conn: Connection, id_empresa: int) -> Inicio:
    corte = q.rango_datos(conn, id_empresa)[1]
    if corte is None:
        return Inicio(tiene_datos=False)
    u = umbrales_empresa(conn, id_empresa)
    desde, hasta = corte.replace(day=1), corte
    mes = _nombre_mes(desde, hasta)

    res = fin.resumen(conn, id_empresa, desde, hasta)
    k = res.kpis
    estado, frase = estado_del_mes(k.ventas, k.utilidad, res.variaciones.ventas, mes, u)
    como = ComoTeFue(mes=mes, ventas=k.ventas, te_quedo=k.utilidad, gastaste=k.costo_ventas + k.gastos_operacion,
                     cambio_ventas=res.variaciones.ventas, estado=estado, frase=frase)

    serie = fin.serie(conn, id_empresa, sumar_meses(desde, -(MESES_GRAFICA - 1)), hasta, "mes")
    ventas_mes = [MesVentas(etiqueta=MESES[int(p.periodo[5:7]) - 1][:3].capitalize(), ventas=p.ventas,
                            actual=i == len(serie) - 1) for i, p in enumerate(serie)]

    prods = fin.productos(conn, id_empresa, desde, hasta, u.dias_inventario_bajo)
    productos = []
    for p in sorted(prods.productos, key=lambda p: p.utilidad, reverse=True)[:MAX_PRODUCTOS]:
        pide = cantidad_a_pedir(p.venta_diaria, p.stock_actual)
        consejo_estado, consejo = consejo_producto(p.precio_venta, p.costo_promedio, p.venta_diaria, p.dias_inventario,
                                                   p.semaforo, pide, p.unidad, u)
        productos.append(ProductoSencillo(
            nombre=p.nombre, unidad=p.unidad, vendiste=p.unidades, te_dejo=p.utilidad, inventario=p.semaforo,
            precio=p.precio_venta, costo=p.costo_promedio, te_quedan=p.stock_actual, dias_te_alcanzan=p.dias_inventario,
            pide=pide, consejo=consejo, consejo_estado=consejo_estado))

    lo_que_viene = None
    pr = proy_srv.proyeccion(conn, id_empresa)
    if pr.get("tiene_datos"):
        fl, inv = pr["flujo"], pr["inventario"]
        compras = [Compra(nombre=p["nombre"], cantidad=p["cantidad_sugerida"], unidad=p["unidad"], costo=p["costo_compra"])
                   for p in inv["productos"] if p["cantidad_sugerida"] > 0][:MAX_COMPRAS]
        lo_que_viene = LoQueViene(
            mes=pr["mes"]["etiqueta"].split(" ")[0].lower(), ventas_esperadas=pr["mes"]["ventas"],
            ganancia_esperada=pr["mes"]["utilidad"], efectivo_hoy=fl["efectivo_actual"],
            efectivo_fin_de_mes=fl["fin_de_mes"]["esperado"], te_alcanza=fl["fecha_riesgo"] is None,
            fecha_riesgo=fl["fecha_riesgo"], comprar=compras, total_compra=round(sum(c.costo for c in compras), 2))

    impuestos = None
    imp = imp_srv.calcular(conn, id_empresa)
    if imp.get("tiene_datos"):
        h = imp["hasta_la_anual"]
        impuestos = ImpuestosSencillo(
            mes=imp["mes_etiqueta"], a_pagar=imp["total_a_pagar"], fecha_limite=imp["fecha_limite"],
            saldo_a_favor=imp["saldo_a_favor"], regimen=imp["configuracion"]["regimen_nombre"],
            periodo_desde=imp["periodo_desde"], periodo_hasta=imp["periodo_hasta"],
            hasta_la_anual=HastaLaAnual(fecha_anual=h["hasta"], pagos_mensuales=h["pagos_mensuales"], total_mensuales=h["total_mensuales"],
                                        ajuste_anual=h["ajuste_anual"], total=h["total"]))

    deudas = None
    dp = deudas_srv.panel(conn, id_empresa)
    if dp.get("hay_deudas"):
        proximos = sorted((d for d in dp["deudas"] if d.get("proximo_pago")), key=lambda d: d["proximo_pago"]["fecha"])
        orden = dp["estrategias"][dp["estrategias"]["recomendada"]]["orden"]
        deudas = DeudasSencillo(
            total=dp["kpis"]["deuda_total"], pago_del_mes=dp["kpis"]["pago_mensual_total"],
            paga_primero=orden[0] if orden else None,
            proximo_pago={"acreedor": proximos[0]["acreedor"], **proximos[0]["proximo_pago"]} if proximos else None)

    return Inicio(tiene_datos=True, como_te_fue=como, ventas_por_mes=ventas_mes, productos=productos,
                  lo_que_viene=lo_que_viene, impuestos=impuestos, deudas=deudas)
