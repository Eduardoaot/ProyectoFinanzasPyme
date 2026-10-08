// Tipos de las respuestas de Proyecciones, Impuestos y Deudas. Todas las cifras vienen calculadas del backend.

import type { Alerta, Semaforo } from "./tipos";

export interface ClaraTexto {
  texto: string;
  redactado_por_ia: boolean;
  aviso: string;
}

/* ---------- Proyecciones ---------- */

export interface PuntoSemana {
  fecha: string;
  real: number | null;
  pronostico: number | null;
  pesimista: number | null;
  optimista: number | null;
}

export interface PuntoEfectivo {
  fecha: string;
  esperado: number;
  pesimista: number;
  optimista: number;
}

export interface FilaReabasto {
  id_producto: number;
  nombre: string;
  unidad: string;
  existencias: number;
  demanda_diaria: number;
  cobertura_dias: number | null;
  fecha_agotamiento: string | null;
  lead_time: number;
  stock_seguridad: number;
  punto_reorden: number;
  cantidad_sugerida: number;
  costo_compra: number;
  semaforo: Semaforo;
  excesivo: boolean;
  monto_detenido: number;
  posponer: boolean;
  ganancia_por_unidad: number;
}

export interface ParteReparto {
  clave: "impuestos" | "deuda_obligatoria" | "deuda_extra" | "fondo_emergencia" | "reinversion" | "retiro";
  deseado: number;
  asignado: number;
}

export interface Proyecciones {
  tiene_datos: boolean;
  fecha_corte: string;
  pronostico: {
    metodo: string;
    pocos_datos: boolean;
    aviso: string | null;
    precision: number | null;
    venta_base_diaria: number;
    sigma_diaria: number;
    semanas: PuntoSemana[];
    total_horizonte: number;
    total_horizonte_pesimista: number;
    total_horizonte_optimista: number;
    semanas_horizonte: number;
  };
  mes: {
    etiqueta: string;
    desde: string;
    hasta: string;
    ventas_reales_a_la_fecha: number;
    ventas: number;
    ventas_pesimista: number;
    ventas_optimista: number;
    costo: number;
    gastos_fijos: number;
    gastos_variables: number;
    utilidad: number;
    utilidad_pesimista: number;
    utilidad_optimista: number;
    margen_bruto: number;
  };
  flujo: {
    efectivo_actual: number;
    minimo_seguridad: number;
    serie: PuntoEfectivo[];
    fin_de_mes: { fecha: string; esperado: number; pesimista: number; optimista: number };
    dias_colchon: number | null;
    fecha_riesgo: string | null;
    causa_riesgo: { monto: number; concepto: string } | null;
  };
  equilibrio: {
    mensual: number | null;
    diario: number | null;
    gastos_operacion_mensuales: number;
    margen_bruto: number;
    margen_seguridad: number | null;
    dia_cubierto: string | null;
    faltante: number;
    avance: number;
    ventas_proyectadas: number;
  };
  inventario: {
    productos: FilaReabasto[];
    presupuesto: number;
    total_compra_sugerida: number;
    alcanza: boolean;
    pospuestos: string[];
    monto_excesivo: number;
    factor_tendencia: number;
  };
  consejos: {
    apartado_impuestos: number;
    fondo_emergencia: { meta: number; actual: number; avance: number; ahorro_mensual_6_meses: number };
    reserva_inventario: number;
    utilidad_proyectada: number;
    distribucion: ParteReparto[];
    faltante_obligatorio: number;
    pago_deuda_mensual: number;
    pago_extra_deuda_sugerido: number;
  };
  alertas: Alerta[];
}

export interface EscenarioEntrada {
  ventas_pct: number;
  precios_pct: number;
  gasto_fijo_extra: number;
  deuda_monto: number;
  deuda_tasa: number;
  deuda_plazo: number;
}

/* ---------- Impuestos ---------- */

export interface MesImpuestos {
  periodo: string;
  etiqueta: string;
  ventas: number;
  ingresos: number;
  iva_trasladado: number;
  iva_acreditable: number;
  iva_a_pagar: number;
  saldo_a_favor: number;
  isr: number;
  total: number;
  fecha_limite: string;
  deducciones: number;
}

export interface ConfigFiscal {
  regimen: "626" | "612" | "601";
  regimen_nombre?: string;
  tipo_persona: "fisica" | "moral";
  factura_a_morales: boolean;
  pct_ventas_morales: number;
  tiene_trabajadores: boolean;
  coeficiente_utilidad: number;
}

export interface Impuestos {
  tiene_datos: boolean;
  aviso_legal: string;
  mes: string;
  mes_etiqueta: string;
  configuracion: ConfigFiscal & { regimen_nombre: string };
  total_a_pagar: number;
  isr: number;
  iva_a_pagar: number;
  saldo_a_favor: number;
  fecha_limite: string;
  apartar_por_cada_100: number | null;
  tasa_efectiva_anual: number | null;
  total_acumulado_anio: number;
  meses: MesImpuestos[];
  perdido_por_no_deducir: { monto: number; isr: number; iva: number; gastos: number; tasa_marginal: number; sin_cfdi: number; efectivo: number };
  comparador_regimen: {
    resico_anual: number;
    actividades_empresariales_anual: number;
    ahorro: number;
    elegible_resico: boolean;
    conviene: "resico" | "actividades_empresariales";
    actual: "resico" | "actividades_empresariales";
    nota: string;
  } | null;
  ptu: { anual_estimada: number; provision_mensual: number; fecha: string } | null;
  limite_resico: { estado: "ok" | "cerca" | "excedido"; ingresos_acumulados: number; limite: number; proyeccion_anual: number } | null;
  calendario: { fecha: string; concepto: string; monto: number | null; estimado: boolean }[];
  explicacion_iva: string | null;
  mensaje_resico: string | null;
}

export interface GastoClasificado {
  id_gasto: number;
  fecha: string;
  concepto: string;
  categoria: string;
  monto: number;
  tiene_cfdi: boolean;
  medio_pago: "efectivo" | "transferencia" | "tarjeta" | "cheque";
  uso: "negocio" | "personal";
  estado: "deducible" | "parcial" | "no_deducible";
  porcentaje: number;
  monto_deducible: number;
  motivo: string;
  acredita_iva: boolean;
  corregible: "sin_cfdi" | "efectivo" | null;
}

/* ---------- Deudas ---------- */

export type TipoDeuda = "tarjeta_credito" | "credito_simple" | "credito_revolvente" | "proveedor" | "prestamo_personal" | "arrendamiento";

export interface Deuda {
  id_deuda: number;
  acreedor: string;
  tipo: TipoDeuda;
  tipo_texto: string;
  monto_original: number;
  saldo_actual: number;
  tasa_interes_anual: number;
  cat: number | null;
  aplica_iva_intereses: boolean;
  plazo_meses: number | null;
  pago_mensual: number;
  pago_mensual_capturado: number | null;
  limite_credito: number | null;
  fecha_inicio: string;
  dia_corte: number | null;
  dia_limite_pago: number | null;
  comisiones_mensuales: number;
  tasa_moratoria_anual: number | null;
  uso: "negocio" | "personal";
  estado: "activa" | "liquidada" | "vencida";
  progreso: number | null;
  utilizacion: number | null;
  pago_minimo: number | null;
  pago_sin_intereses: number | null;
  nunca_baja: boolean;
  meses_para_liquidar: number | null;
  fecha_liquidacion: string | null;
  interes_total: number;
  proximo_pago: { fecha: string; monto: number };
}

export interface PlanPago {
  interes_total: number;
  meses: number | null;
  fecha_liquidacion: string | null;
  orden: string[];
}

export interface PanelDeudas {
  hay_deudas: boolean;
  fecha_corte: string;
  deudas: Deuda[];
  liquidadas?: string[];
  alertas: Alerta[];
  kpis: {
    deuda_total: number;
    deuda_corto_plazo: number;
    pago_mensual_total: number;
    proximos_pagos: { "7_dias": number; "30_dias": number };
    tasa_promedio_ponderada: number | null;
    costo_mensual: number;
    pct_ventas: number | null;
    semaforo_pct_ventas: Semaforo;
    dscr: number | null;
    semaforo_dscr: Semaforo;
    razon_deuda_utilidad_anual: number | null;
    fecha_libre: string | null;
    capacidad_endeudamiento: { pago_maximo: number; monto_equivalente: number; plazo_meses: number };
    utilizacion_tarjetas: number | null;
    utilidad_operativa_mensual: number;
    ventas_mensuales: number;
  } | null;
  estrategias?: {
    extra_mensual: number;
    actual: PlanPago;
    avalancha: PlanPago;
    bola_de_nieve: PlanPago;
    recomendada: "avalancha" | "bola_de_nieve";
    ahorro_avalancha_vs_bola: number;
  };
  saldo_series?: { mes: number; fecha: string; actual: number; avalancha: number; bola_de_nieve: number }[];
  barras_pago?: { mes: number; etiqueta: string; capital: number; interes: number }[];
  calendario?: { fecha: string; acreedor: string; monto: number }[];
}
