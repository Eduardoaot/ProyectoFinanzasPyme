"""Alertas deterministas (CLAUDE.md §7).

El código detecta cada alerta y calcula sus cifras. El texto base (plantilla) siempre existe;
el LLM solo puede reescribirlo con las mismas cifras (ver alerts/redaccion.py).
"""

import json
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import Connection

from app.config import UmbralesAlerta, get_settings
from app.finance import consultas as q
from app.finance import servicio
from app.finance.formato import dinero, numero, pct, pct_cambio, unidades
from app.finance.periodos import describir_periodo, periodo_anterior

Nivel = Literal["rojo", "amarillo", "verde"]
ORDEN_NIVEL = {"rojo": 0, "amarillo": 1, "verde": 2}
MAX_POR_TIPO = 3


class Alerta(BaseModel):
    id: str
    codigo: str
    nivel: Nivel
    titulo: str
    mensaje: str
    accion: str
    modulo: Literal["resumen", "finanzas", "productos", "flujo", "proyecciones", "impuestos", "deudas"]
    metricas: dict[str, str]
    redactado_por_ia: bool = False


def umbrales_empresa(conn: Connection, id_empresa: int) -> UmbralesAlerta:
    """Umbrales por defecto + los que la empresa haya personalizado."""
    base = get_settings().umbrales.model_dump()
    propios = (q.empresa(conn, id_empresa) or {}).get("umbrales_alerta")
    if isinstance(propios, str):
        propios = json.loads(propios or "null")
    if isinstance(propios, dict):
        base.update({k: float(v) for k, v in propios.items() if k in base})
    return UmbralesAlerta(**base)


def evaluar(conn: Connection, id_empresa: int, desde: date, hasta: date) -> list[Alerta]:
    u = umbrales_empresa(conn, id_empresa)
    alertas: list[Alerta] = []
    periodo = describir_periodo(desde, hasta)
    ant_desde, ant_hasta = periodo_anterior(desde, hasta)
    periodo_ant = describir_periodo(ant_desde, ant_hasta)
    res = servicio.resumen(conn, id_empresa, desde, hasta)
    k, var = res.kpis, res.variaciones

    # 🔴 / 🟢 Rentabilidad de la empresa
    if k.ventas > 0 and k.margen is not None:
        if k.utilidad < 0:
            alertas.append(Alerta(
                id="margen_neto_bajo", codigo="margen_neto_bajo", nivel="rojo", modulo="finanzas",
                titulo="Este periodo perdiste dinero",
                mensaje=f"En {periodo} vendiste {dinero(k.ventas)}, pero entre mercancía y gastos se fue más de lo "
                        f"que entró: perdiste {dinero(-k.utilidad)}.",
                accion="Revisa tus gastos más grandes y los productos que menos te dejan.",
                metricas={"periodo": periodo, "ventas": dinero(k.ventas), "perdida": dinero(-k.utilidad),
                          "margen": pct(k.margen), "gastos_operacion": dinero(k.gastos_operacion)},
            ))
        elif k.margen < u.margen_neto_bajo:
            alertas.append(Alerta(
                id="margen_neto_bajo", codigo="margen_neto_bajo", nivel="rojo", modulo="finanzas",
                titulo="Tu margen está bajo",
                mensaje=f"De cada $100 que vendiste en {periodo} te quedaron {dinero(k.margen * 100)}. "
                        f"Tu margen es {pct(k.margen)} y conviene que esté arriba de {pct(u.margen_neto_bajo, 0)}.",
                accion="Revisa precios de los productos con menor margen y tus gastos fijos.",
                metricas={"periodo": periodo, "margen": pct(k.margen), "umbral": pct(u.margen_neto_bajo, 0),
                          "de_cada_100": dinero(k.margen * 100), "utilidad": dinero(k.utilidad), "ventas": dinero(k.ventas)},
            ))
        elif k.margen >= u.buena_rentabilidad:
            alertas.append(Alerta(
                id="buena_rentabilidad", codigo="buena_rentabilidad", nivel="verde", modulo="finanzas",
                titulo="¡Buena rentabilidad!",
                mensaje=f"En {periodo} ganaste {dinero(k.utilidad)}: de cada $100 que vendiste te quedaron "
                        f"{dinero(k.margen * 100)} (margen de {pct(k.margen)}).",
                accion="Sigue así; aparta una parte para imprevistos.",
                metricas={"periodo": periodo, "utilidad": dinero(k.utilidad), "margen": pct(k.margen),
                          "de_cada_100": dinero(k.margen * 100)},
            ))

    # 🟡 / 🟢 Tendencia de ventas
    if var.ventas is not None:
        if var.ventas <= -u.caida_ventas:
            alertas.append(Alerta(
                id="caida_ventas", codigo="caida_ventas", nivel="amarillo", modulo="resumen",
                titulo="Tus ventas bajaron",
                mensaje=f"Vendiste {dinero(k.ventas)} en {periodo}, {pct_cambio(var.ventas)} frente a "
                        f"{periodo_ant} ({dinero(res.kpis_anterior.ventas)}).",
                accion="Compara con la misma temporada del año pasado: puede ser estacional.",
                metricas={"periodo": periodo, "periodo_anterior": periodo_ant, "ventas": dinero(k.ventas),
                          "ventas_anterior": dinero(res.kpis_anterior.ventas), "cambio": pct_cambio(var.ventas)},
            ))
        elif var.ventas >= u.crecimiento_ventas:
            alertas.append(Alerta(
                id="ventas_crecen", codigo="ventas_crecen", nivel="verde", modulo="resumen",
                titulo="Tus ventas van creciendo",
                mensaje=f"Vendiste {dinero(k.ventas)} en {periodo}, {pct_cambio(var.ventas)} frente a {periodo_ant}.",
                accion="Asegura inventario de tus productos más vendidos.",
                metricas={"periodo": periodo, "periodo_anterior": periodo_ant, "ventas": dinero(k.ventas),
                          "cambio": pct_cambio(var.ventas)},
            ))

    # 🟡 Gastos crecen más rápido que las ventas
    # (solo si los gastos de verdad crecieron; una caída de ventas sola ya tiene su propia alerta)
    if var.gastos_operacion is not None and var.ventas is not None and var.gastos_operacion > u.gastos_vs_ventas_pp \
            and var.gastos_operacion - var.ventas > u.gastos_vs_ventas_pp:
        alertas.append(Alerta(
            id="gastos_vs_ventas", codigo="gastos_vs_ventas", nivel="amarillo", modulo="finanzas",
            titulo="Tus gastos crecen más rápido que tus ventas",
            mensaje=f"Tus gastos de operación cambiaron {pct_cambio(var.gastos_operacion)} y tus ventas "
                    f"{pct_cambio(var.ventas)} frente a {periodo_ant}. Gastaste {dinero(k.gastos_operacion)} en {periodo}.",
            accion="Identifica qué gasto nuevo apareció y si ya está dando resultados.",
            metricas={"periodo": periodo, "periodo_anterior": periodo_ant, "cambio_gastos": pct_cambio(var.gastos_operacion),
                      "cambio_ventas": pct_cambio(var.ventas), "gastos": dinero(k.gastos_operacion)},
        ))

    # 🔴 Productos con margen muy bajo · 🔴 Inventario por agotarse
    prods = servicio.productos(conn, id_empresa, desde, hasta, u.dias_inventario_bajo)
    bajos = sorted((p for p in prods.productos if p.ventas > 0 and p.margen_actual is not None
                    and p.margen_actual < u.margen_producto_bajo), key=lambda p: p.margen_actual or 0)
    for p in bajos[:MAX_POR_TIPO]:
        ganancia = p.precio_venta - p.costo_promedio
        alertas.append(Alerta(
            id=f"producto_margen_bajo:{p.id_producto}", codigo="producto_margen_bajo", nivel="rojo", modulo="productos",
            titulo=f"{p.nombre} casi no te deja ganancia",
            mensaje=f"Lo vendes en {dinero(p.precio_venta)} y te cuesta {dinero(p.costo_promedio)}: te quedan "
                    f"{dinero(ganancia)} por {p.unidad} (margen de {pct(p.margen_actual)}).",
            accion="Valora subir un poco el precio o buscar otro proveedor.",
            metricas={"producto": p.nombre, "precio": dinero(p.precio_venta), "costo": dinero(p.costo_promedio),
                      "ganancia_unitaria": dinero(ganancia), "margen": pct(p.margen_actual),
                      "umbral": pct(u.margen_producto_bajo, 0)},
        ))

    por_agotarse = sorted((p for p in prods.productos if p.semaforo == "rojo"), key=lambda p: p.dias_inventario or 0)
    if por_agotarse:
        detalle = ", ".join(f"{p.nombre} ({unidades(p.stock_actual, p.unidad)}, ~{numero(p.dias_inventario)} días)"
                            for p in por_agotarse[:5])
        alertas.append(Alerta(
            id="inventario_bajo", codigo="inventario_bajo", nivel="rojo", modulo="productos",
            titulo=f"Tienes {len(por_agotarse)} producto{'s' if len(por_agotarse) > 1 else ''} por agotarse",
            mensaje=f"Al ritmo de venta actual se acaban pronto: {detalle}.",
            accion="Haz tu pedido al proveedor esta semana.",
            metricas={"cantidad": str(len(por_agotarse)), "productos": detalle},
        ))

    # 🟡 Costo de mercancía subió y el precio no
    actuales = q.precios_por_producto(conn, id_empresa, desde, hasta)
    previos = q.precios_por_producto(conn, id_empresa, ant_desde, ant_hasta)
    nombres = {p.id_producto: p for p in prods.productos}
    subidas = []
    for id_p, a in actuales.items():
        b = previos.get(id_p)
        if not b or b["costo"] == 0 or b["precio"] == 0:
            continue
        cambio_costo = float((a["costo"] - b["costo"]) / b["costo"])
        cambio_precio = float((a["precio"] - b["precio"]) / b["precio"])
        margen_antes = float((b["precio"] - b["costo"]) / b["precio"])
        margen_ahora = float((a["precio"] - a["costo"]) / a["precio"])
        # Solo cuando el margen de verdad se come (≥ 2 puntos); evita ruido de centavos.
        if cambio_costo >= u.subida_costo and cambio_precio < 0.01 and margen_antes - margen_ahora >= 0.02:
            subidas.append((cambio_costo, cambio_precio, id_p, a, b))
    for cambio_costo, cambio_precio, id_p, a, b in sorted(subidas, reverse=True)[:MAX_POR_TIPO]:
        p = nombres[id_p]
        margen_nuevo = float((a["precio"] - a["costo"]) / a["precio"])
        alertas.append(Alerta(
            id=f"costo_sube:{id_p}", codigo="costo_sube_precio_no", nivel="amarillo", modulo="productos",
            titulo=f"Subió el costo de {p.nombre}",
            mensaje=f"Tu costo de {p.nombre} subió {pct_cambio(cambio_costo)} (de {dinero(float(b['costo']))} a "
                    f"{dinero(float(a['costo']))}) pero tu precio sigue en {dinero(float(a['precio']))}. "
                    f"Su margen bajó a {pct(margen_nuevo)}.",
            accion="Revisa si puedes ajustar el precio o negociar con tu proveedor.",
            metricas={"producto": p.nombre, "cambio_costo": pct_cambio(cambio_costo), "costo_antes": dinero(float(b["costo"])),
                      "costo_ahora": dinero(float(a["costo"])), "precio": dinero(float(a["precio"])), "margen": pct(margen_nuevo)},
        ))

    # 🔴 / 🟡 Flujo de efectivo proyectado
    proy = servicio.proyeccion(conn, id_empresa)
    if proy:
        metricas = {"saldo_actual": dinero(proy.saldo_actual), "saldo_30_dias": dinero(proy.saldo_proyectado),
                    "entradas_diarias": dinero(proy.entradas_diarias), "salidas_diarias": dinero(proy.salidas_diarias),
                    "escenario_bajo": dinero(proy.inferior), "fecha_corte": f"{proy.fecha_corte:%d/%m/%Y}"}
        if proy.saldo_proyectado < 0:
            alertas.append(Alerta(
                id="flujo_negativo", codigo="flujo_negativo", nivel="rojo", modulo="flujo",
                titulo="Tu efectivo podría no alcanzar en 30 días",
                mensaje=f"Tienes {dinero(proy.saldo_actual)} y, si sigues al ritmo de los últimos 30 días "
                        f"(entran {dinero(proy.entradas_diarias)} y salen {dinero(proy.salidas_diarias)} al día), "
                        f"en 30 días tendrías {dinero(proy.saldo_proyectado)}.",
                accion="Pospón compras que no sean urgentes y cobra lo pendiente. Puedes evaluar un financiamiento "
                       "de corto plazo; compara costos y plazos antes de decidir.",
                metricas=metricas,
            ))
        elif proy.inferior < 0:
            alertas.append(Alerta(
                id="flujo_ajustado", codigo="flujo_ajustado", nivel="amarillo", modulo="flujo",
                titulo="Tu efectivo viene justo",
                mensaje=f"En 30 días esperarías tener {dinero(proy.saldo_proyectado)}, pero en un mes flojo podrías "
                        f"llegar a {dinero(proy.inferior)}.",
                accion="Arma un pequeño colchón antes de hacer compras grandes.",
                metricas=metricas,
            ))

    alertas.sort(key=lambda a: ORDEN_NIVEL[a.nivel])
    return alertas
