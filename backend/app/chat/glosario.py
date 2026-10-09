"""Glosario de Clara: definiciones escritas por personas, no por el LLM.

Cuando el dueño pregunta "¿qué significa X?", Clara muestra esta definición y, si existe, la conecta
con las cifras reales del negocio (`datos` dice qué cálculo usar). El LLM solo la redacta en
palabras más cercanas; la guardia de cifras impide que agregue números.
"""

import re
from dataclasses import dataclass

DISPARADORES = ("que significa", "que significan", "que es ", "que son ", "explicame", "explica", "me explicas",
                "que quiere decir", "a que se refiere", "como se calcula", "como funciona", "definicion",
                "define ", "no entiendo", "para que sirve", "diferencia entre", "en que consiste")


@dataclass(frozen=True)
class Concepto:
    clave: str
    titulo: str
    alias: tuple[str, ...]          # sin acentos y en minúsculas
    definicion: str
    ejemplo: str = ""
    donde: str = ""
    datos: str | None = None        # "deudas", "equilibrio", "margen", "inventario", "flujo", "impuestos", "pronostico"


GLOSARIO: tuple[Concepto, ...] = (
    # ---------------------------------------------------------------- deudas
    Concepto(
        "bola_de_nieve", "Bola de nieve", ("bola de nieve",),
        "Es una forma de pagar varias deudas: pagas lo mínimo en todas y todo el dinero extra lo mandas a la deuda "
        "con el saldo más pequeño. Cuando la terminas, lo que pagabas en ella se suma al abono de la siguiente más "
        "pequeña, y el abono va creciendo como una bola de nieve.",
        "Ventaja: liquidas deudas pronto y eso motiva. Desventaja: casi siempre pagas más intereses que con avalancha, "
        "porque la deuda más cara se queda para después.",
        "Deudas → gráfica «Saldo proyectado», línea bola de nieve.", "deudas"),
    Concepto(
        "avalancha", "Avalancha", ("avalancha", "abalancha"),
        "Es otra forma de pagar varias deudas: pagas lo mínimo en todas y todo el dinero extra lo mandas a la deuda "
        "con la tasa de interés más alta. Cuando la terminas, ese dinero pasa a la siguiente más cara.",
        "Ventaja: es el plan con el que pagas menos intereses en total. Desventaja: si la deuda más cara es grande, "
        "tardas más en ver la primera deuda liquidada.",
        "Deudas → gráfica «Saldo proyectado», línea avalancha.", "deudas"),
    Concepto(
        "saldo_proyectado", "Saldo proyectado", ("saldo proyectado", "saldos proyectados"),
        "Es una estimación de cuánto vas a deber (en Deudas) o cuánto efectivo vas a tener (en Flujo y Proyecciones) "
        "mes a mes si sigues al mismo ritmo. No es un dato real todavía: es lo que pasaría si nada cambia.",
        "En Deudas la gráfica compara tres planes: seguir pagando lo mismo (actual), avalancha y bola de nieve. "
        "El punto donde cada línea llega a cero es el mes en que quedarías libre de deudas con ese plan.",
        "Deudas → «Saldo proyectado» y Flujo de efectivo → proyección.", "deudas"),
    Concepto(
        "dscr", "Cobertura de deuda (DSCR)", ("dscr", "cobertura de deuda", "cobertura del servicio", "cobertura de la deuda"),
        "Dice cuántas veces tu utilidad del mes alcanza para pagar tus deudas del mes: utilidad ÷ pagos de deuda. "
        "1.25 o más es sano, entre 1 y 1.25 es justo, y menos de 1 significa que la utilidad no alcanza.",
        "Si ganas $25,000 al mes y pagas $10,000 de deudas, tu cobertura es 2.5: tu utilidad cubre tus pagos dos veces y media.",
        "Deudas → indicadores.", "deudas"),
    Concepto(
        "cat", "CAT (costo anual total)", ("cat", "costo anual total"),
        "Es el costo total de un crédito en un año, en porcentaje: incluye intereses, comisiones y seguros. "
        "Sirve para comparar créditos entre sí: el de CAT más bajo te cuesta menos.",
        "Dos créditos con la misma tasa pueden tener distinto CAT si uno cobra comisión por apertura.",
        "Deudas → detalle de cada deuda."),
    Concepto(
        "tasa_ponderada", "Tasa promedio ponderada", ("tasa promedio ponderada", "tasa ponderada", "tasa promedio"),
        "Es el interés promedio de todas tus deudas, dándole más peso a las que tienen saldo más grande: "
        "suma de (saldo × tasa) ÷ suma de saldos.",
        donde="Deudas → indicadores.", datos="deudas"),
    Concepto(
        "utilizacion", "Utilización de la tarjeta", ("utilizacion", "uso del limite"),
        "Es qué parte del límite de tu tarjeta estás usando: saldo ÷ límite. Arriba de 30% conviene bajarla, "
        "porque pesa en tu historial de crédito y te deja sin margen para imprevistos.",
        donde="Deudas → tarjetas."),
    Concepto(
        "pago_minimo", "Pago mínimo", ("pago minimo",),
        "Es lo menos que el banco te deja pagar de la tarjeta sin cobrarte moratorios. Si solo pagas el mínimo, "
        "la mayor parte se va a intereses y la deuda casi no baja.",
        donde="Deudas → tarjetas."),
    # ---------------------------------------------------------------- resultados
    Concepto(
        "margen", "Margen", ("margen", "margenes", "porcentaje de ganancia", "margen de utilidad"),
        "Es cuánto te queda de cada $100 que vendes. El margen del negocio es lo que ganaste ÷ ventas. "
        "El margen de un producto es (precio − costo) ÷ precio.",
        "Si vendes una libreta en $50 y te costó $30, te quedan $20: su margen es 40%.",
        "Resumen (margen del negocio) y Productos (margen por producto).", "margen"),
    Concepto(
        "utilidad_bruta", "Utilidad bruta", ("utilidad bruta", "ganancia bruta", "margen bruto"),
        "Es lo que te queda de tus ventas después de pagar la mercancía que vendiste, antes de renta, sueldos y "
        "otros gastos: ventas − costo de la mercancía vendida.",
        donde="Resumen y Finanzas → estado de resultados.", datos="margen"),
    Concepto(
        "utilidad", "Utilidad", ("utilidad", "utilidad operativa", "utilidad neta", "utilidad antes de impuestos"),
        "Es lo que realmente ganaste: ventas − mercancía − gastos del negocio. Si además se restan impuestos, "
        "es la utilidad después de impuestos.",
        donde="Resumen → «Lo que ganaste».", datos="margen"),
    Concepto(
        "estado_resultados", "Estado de resultados", ("estado de resultados",),
        "Es la lista ordenada de lo que vendiste, lo que te costó y lo que te quedó en un periodo: ventas, costo de "
        "la mercancía, utilidad bruta, gastos, impuestos y utilidad.",
        donde="Finanzas.", datos="margen"),
    Concepto(
        "punto_equilibrio", "Punto de equilibrio", ("punto de equilibrio", "equilibrio"),
        "Es lo mínimo que necesitas vender al mes para no perder ni ganar. Se calcula: gastos fijos ÷ margen de "
        "contribución.",
        "Si tus gastos fijos son $10,000 y de cada $100 que vendes te quedan $40 para cubrirlos, necesitas vender "
        "$25,000 al mes para quedar tablas.",
        "Finanzas → punto de equilibrio.", "equilibrio"),
    Concepto(
        "margen_contribucion", "Margen de contribución", ("margen de contribucion", "contribucion"),
        "De cada $100 que vendes, es lo que queda después de pagar la mercancía y los gastos que suben con las "
        "ventas (bolsas, comisiones, fletes). Ese dinero es el que paga la renta, los sueldos y demás gastos fijos.",
        donde="Finanzas → punto de equilibrio.", datos="equilibrio"),
    Concepto(
        "margen_seguridad", "Margen de seguridad", ("margen de seguridad",),
        "Es cuánto podrían bajar tus ventas antes de empezar a perder: ventas actuales − punto de equilibrio.",
        donde="Finanzas y Proyecciones.", datos="equilibrio"),
    Concepto(
        "gastos_fijos_variables", "Gastos fijos y variables", ("gastos fijos", "gastos variables", "gasto fijo", "gasto variable"),
        "Los gastos fijos los pagas aunque no vendas nada (renta, sueldos base, luz, internet). Los variables suben o "
        "bajan con tus ventas o tu actividad (bolsas, fletes, comisiones, mantenimiento).",
        donde="Finanzas → distribución de gastos."),
    # ---------------------------------------------------------------- efectivo
    Concepto(
        "flujo_efectivo", "Flujo de efectivo", ("flujo de efectivo", "flujo de caja", "flujo"),
        "Es el dinero que de verdad entra y sale de tu caja. Es distinto de la utilidad: puedes estar ganando y aun "
        "así quedarte sin efectivo si compras mucha mercancía o pagas deudas grandes.",
        donde="Flujo de efectivo.", datos="flujo"),
    Concepto(
        "capital_trabajo", "Capital de trabajo", ("capital de trabajo",),
        "Es el dinero que necesitas para operar día a día: comprar mercancía y pagar gastos antes de recuperar ese "
        "dinero con las ventas.",
        donde="Flujo de efectivo y Proyecciones.", datos="flujo"),
    Concepto(
        "fondo_emergencia", "Fondo de emergencia", ("fondo de emergencia", "colchon", "dias de colchon"),
        "Es dinero apartado para meses malos o imprevistos. La meta que usa el sistema es 3 meses de gastos fijos más "
        "pagos de deuda. Los «días de colchón» son cuántos días podrías operar con tu efectivo actual sin vender nada.",
        donde="Proyecciones y consejos → ahorro."),
    # ---------------------------------------------------------------- estadística y pronósticos
    Concepto(
        "promedio_movil", "Promedio móvil", ("promedio movil", "linea base"),
        "Es el promedio de los últimos 30 días, que se repite hacia adelante como estimación. Es simple y estable, "
        "pero no ve temporadas (regreso a clases, diciembre) ni tendencias.",
        donde="Flujo de efectivo → proyección a 30 días y detalle de cada producto.", datos="flujo"),
    Concepto(
        "pronostico", "Pronóstico de ventas", ("pronostico", "proyeccion de ventas", "como se proyecta", "como pronostica"),
        "En Proyecciones se estima cada día así: venta base (promedio de las últimas 8 semanas) × índice del día de "
        "la semana (cuánto vende ese día frente a uno normal) + tendencia (si las ventas semanales vienen subiendo o "
        "bajando en las últimas 12 semanas, limitada a ±15%).",
        "Si vendes $1,000 en un día normal y los sábados tienen índice 1.4, el sábado se estima en $1,400.",
        "Proyecciones y consejos.", "pronostico"),
    Concepto(
        "rango_probable", "Rango probable (pesimista y optimista)",
        ("rango probable", "pesimista", "optimista", "escenario pesimista", "escenario optimista", "banda", "intervalo"),
        "Es el margen de error de una estimación: 8 de cada 10 veces el resultado real debería quedar entre el "
        "escenario pesimista y el optimista. Se calcula con lo que normalmente se desvían tus ventas "
        "(1.28 × desviación estándar); entre más lejos en el futuro, más ancho el rango.",
        donde="Proyecciones y Flujo de efectivo.", datos="pronostico"),
    Concepto(
        "precision", "Precisión del pronóstico", ("precision", "confiabilidad", "que tan confiable", "error del pronostico"),
        "Para medirla, el sistema hace como si no conociera tus últimas 8 semanas, las pronostica y compara contra "
        "lo que realmente vendiste. Una precisión de 90% quiere decir que, en promedio, se equivocó 10% en la venta "
        "de la semana.",
        donde="Proyecciones → pronóstico.", datos="pronostico"),
    Concepto(
        "tendencia", "Tendencia", ("tendencia", "tendencias"),
        "Indica si algo viene subiendo o bajando con el tiempo. Se calcula con la recta que mejor pasa por tus datos "
        "(mínimos cuadrados). El R² dice qué tanto se parecen los datos a esa recta: cerca de 1 es una tendencia "
        "clara, cerca de 0 es puro sube y baja.",
        donde="Proyecciones y la pregunta «¿qué productos van a mejorar?»."),
    Concepto(
        "indice_dia", "Índice del día de la semana", ("indice del dia", "indice semanal", "estacionalidad"),
        "Dice cuánto vende cada día de la semana comparado con un día promedio. Un índice de 1.4 el sábado significa "
        "que el sábado vendes 40% más que un día normal; 0.7 el lunes, 30% menos.",
        donde="Proyecciones → pronóstico."),
    Concepto(
        "desviacion_estandar", "Desviación estándar", ("desviacion estandar", "desviacion", "sigma"),
        "Mide qué tanto se alejan tus ventas de su promedio. Si casi todos los días vendes parecido, es baja; si un día "
        "vendes mucho y otro casi nada, es alta. Con ella se calcula el rango probable y el stock de seguridad.",
        donde="Proyecciones."),
    # ---------------------------------------------------------------- inventario
    Concepto(
        "dias_inventario", "Días de inventario", ("dias de inventario", "cobertura", "dias de cobertura"),
        "Son los días que te alcanza lo que tienes al ritmo de venta actual: existencias ÷ venta diaria promedio.",
        "Si tienes 60 cuadernos y vendes 4 al día, te alcanzan para 15 días.",
        "Productos → columna Inventario.", "inventario"),
    Concepto(
        "valor_inventario", "Dinero en inventario", ("valor del inventario", "valor de inventario", "dinero en inventario",
                                                     "dinero en existencia", "valor de mi inventario"),
        "Es el dinero que tienes «guardado» en mercancía hoy: existencias × lo que te costó cada pieza. Es dinero que "
        "ya pagaste y que recuperas cuando vendes.",
        donde="Productos → tarjetas de arriba.", datos="inventario"),
    Concepto(
        "stock_seguridad", "Stock de seguridad", ("stock de seguridad", "inventario de seguridad", "existencia de seguridad"),
        "Son piezas extra para no quedarte sin producto si vendes más de lo normal mientras llega tu pedido. Se calcula "
        "1.65 × variación diaria de la venta × raíz de los días de entrega, lo que cubre 95 de cada 100 casos.",
        donde="Proyecciones → inventario."),
    Concepto(
        "punto_reorden", "Punto de reorden", ("punto de reorden", "reorden"),
        "Es la cantidad a la que, si tus existencias bajan, ya toca hacer el pedido: venta diaria × días que tarda el "
        "proveedor + stock de seguridad.",
        donde="Proyecciones → inventario."),
    Concepto(
        "inventario_detenido", "Inventario detenido", ("inventario detenido", "dinero detenido", "inventario excesivo"),
        "Es el dinero en piezas que no venderías en los próximos 60 días al ritmo actual. Es efectivo «congelado» que "
        "podrías usar en otra cosa.",
        donde="Proyecciones → inventario.", datos="inventario"),
    Concepto(
        "costo_promedio", "Costo promedio", ("costo promedio",),
        "Es lo que te cuesta en promedio cada pieza, mezclando compras hechas a distintos precios.",
        donde="Productos → detalle de cada producto."),
    # ---------------------------------------------------------------- impuestos
    Concepto(
        "resico", "RESICO", ("resico", "regimen simplificado de confianza"),
        "Es el Régimen Simplificado de Confianza. Las personas físicas pagan ISR con una tasa baja (de 1% a 2.5%) "
        "sobre lo que cobran, sin restar gastos, siempre que sus ingresos no pasen de 3.5 millones al año.",
        donde="Impuestos.", datos="impuestos"),
    Concepto(
        "iva", "IVA trasladado y acreditable", ("iva acreditable", "iva trasladado", "acreditar", "acreditable", "iva"),
        "El IVA trasladado es el que cobras a tus clientes; el acreditable es el que pagas a tus proveedores con "
        "factura. Al SAT le pagas la diferencia; si pagaste más del que cobraste, te queda saldo a favor.",
        donde="Impuestos.", datos="impuestos"),
    Concepto(
        "isr", "ISR", ("isr", "impuesto sobre la renta"),
        "Es el Impuesto Sobre la Renta. Según tu régimen se calcula sobre lo que cobras (RESICO) o sobre tu ganancia "
        "después de gastos deducibles (Actividad Empresarial).",
        donde="Impuestos.", datos="impuestos"),
    Concepto(
        "deducible", "Gasto deducible", ("deducible", "deducibles", "deducir", "deduccion", "deducciones"),
        "Es un gasto del negocio que puedes restar de tus ingresos para pagar menos ISR. Normalmente necesita factura "
        "(CFDI) y, arriba de $2,000, haberse pagado con transferencia o tarjeta, no en efectivo.",
        donde="Impuestos → gastos clasificados.", datos="impuestos"),
)


def _patron(alias: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(alias)}\b")


_PATRONES = [(c, [_patron(a) for a in c.alias]) for c in GLOSARIO]


def buscar(texto_sin_acentos: str, limite: int = 3) -> list[Concepto]:
    """Conceptos mencionados, en el orden en que aparecen. Un alias largo gana a uno corto que contiene
    ("margen de seguridad" no cuenta también como "margen")."""
    encontrados: list[tuple[int, int, Concepto]] = []
    for concepto, patrones in _PATRONES:
        for p in patrones:
            if m := p.search(texto_sin_acentos):
                encontrados.append((m.start(), m.end(), concepto))
                break
    encontrados.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    resultado: list[Concepto] = []
    ocupado: list[tuple[int, int]] = []
    for inicio, fin, concepto in encontrados:
        if any(inicio < f and fin > i for i, f in ocupado) or concepto in resultado:
            continue
        resultado.append(concepto)
        ocupado.append((inicio, fin))
    return resultado[:limite]


def pide_explicacion(texto_sin_acentos: str) -> bool:
    texto = f" {texto_sin_acentos} "
    return any(d in texto for d in DISPARADORES)
