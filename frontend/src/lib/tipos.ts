// Tipos de las respuestas de la API (espejo de los modelos Pydantic del backend).

export interface Usuario {
  id_usuario: number;
  nombre: string;
  email: string;
}

export interface EmpresaResumen {
  id_empresa: number;
  nombre_negocio: string;
  giro: string;
  ciudad: string | null;
  rol: "dueno" | "consulta";
}

export interface Sesion {
  token: string;
  usuario: Usuario;
  empresas: EmpresaResumen[];
}

export interface Umbrales {
  margen_neto_bajo: number;
  margen_producto_bajo: number;
  dias_inventario_bajo: number;
  gastos_vs_ventas_pp: number;
  caida_ventas: number;
  subida_costo: number;
  buena_rentabilidad: number;
  crecimiento_ventas: number;
}

export interface InfoEmpresa {
  id_empresa: number;
  nombre_negocio: string;
  giro: string;
  ciudad: string | null;
  regimen_fiscal: string | null;
  primer_dato: string | null;
  ultimo_dato: string | null;
  tiene_datos: boolean;
  umbrales: Umbrales;
}

export interface Periodo {
  desde: string;
  hasta: string;
  etiqueta: string;
}

export interface KPIs {
  ventas: number;
  costo_ventas: number;
  utilidad_bruta: number;
  gastos_operacion: number;
  gastos_fijos: number;
  gastos_variables: number;
  impuestos: number;
  impuestos_calculados: boolean;
  utilidad: number;
  margen: number | null;
  margen_bruto: number | null;
  unidades: number;
}

export interface Variaciones {
  ventas: number | null;
  costo_ventas: number | null;
  utilidad_bruta: number | null;
  gastos_operacion: number | null;
  utilidad: number | null;
  margen_pp: number | null;
}

export interface PuntoSerie {
  periodo: string;
  etiqueta: string;
  ventas: number;
  costo: number;
  gastos: number;
  utilidad_bruta: number;
  utilidad: number;
}

export interface DatoClave {
  etiqueta: string;
  valor: number | string | null;
  formato: "dinero" | "porcentaje" | "numero" | "texto";
  ayuda: string;
}

export interface Resumen {
  periodo: Periodo;
  periodo_anterior: Periodo;
  kpis: KPIs;
  kpis_anterior: KPIs;
  variaciones: Variaciones;
  serie: PuntoSerie[];
  datos_clave: DatoClave[];
}

export interface LineaEstado {
  clave: string;
  etiqueta: string;
  termino_tecnico: string;
  monto: number;
  porcentaje: number | null;
  nivel: "ingreso" | "resta" | "subtotal" | "total" | "info";
  nota: string;
}

export interface CategoriaGasto {
  categoria: string;
  tipo: string;
  monto: number;
  porcentaje: number;
}

export interface PuntoEquilibrio {
  gastos_fijos_mensuales: number;
  margen_contribucion: number | null;
  punto_equilibrio_mensual: number | null;
  ventas_mensuales_promedio: number;
  margen_seguridad_mensual: number | null;
  cubierto: boolean | null;
}

export interface Finanzas {
  periodo: Periodo;
  estado_resultados: LineaEstado[];
  mensual: PuntoSerie[];
  distribucion_gastos: CategoriaGasto[];
  punto_equilibrio: PuntoEquilibrio;
}

export type Semaforo = "verde" | "amarillo" | "rojo" | "sin_movimiento";

export interface ProductoMetricas {
  id_producto: number;
  nombre: string;
  categoria: string;
  unidad: string;
  unidades: number;
  ventas: number;
  costo: number;
  utilidad: number;
  margen: number | null;
  precio_venta: number;
  costo_promedio: number;
  margen_actual: number | null;
  stock_actual: number;
  stock_minimo: number;
  venta_diaria: number;
  dias_inventario: number | null;
  semaforo: Semaforo;
  valor_inventario: number;
}

export interface Productos {
  periodo: Periodo;
  productos: ProductoMetricas[];
  top_utilidad: ProductoMetricas[];
  bajo_margen: ProductoMetricas[];
  inventario: {
    verde: number;
    amarillo: number;
    rojo: number;
    sin_movimiento: number;
    valor_total: number;
    valor_a_precio_venta: number;
    unidades_total: number;
    compras_periodo: number;
  };
}

export interface PuntoFlujoMensual {
  periodo: string;
  etiqueta: string;
  entradas: number;
  compras: number;
  gastos: number;
  neto: number;
  saldo: number;
}

export interface Proyeccion {
  metodo: string;
  dias: number;
  fecha_corte: string;
  saldo_actual: number;
  saldo_proyectado: number;
  inferior: number;
  superior: number;
  entradas_diarias: number;
  salidas_diarias: number;
  puntos: { fecha: string; saldo: number; inferior: number; superior: number }[];
}

export interface Flujo {
  periodo: Periodo;
  saldo_inicial: number;
  entradas: number;
  compras: number;
  gastos: number;
  saldo_final: number;
  mensual: PuntoFlujoMensual[];
  diario: { fecha: string; saldo: number }[];
  proyeccion: Proyeccion | null;
}

export interface Pronostico {
  metodo: string;
  serie: string;
  id_producto: number | null;
  dias: number;
  historico: { fecha: string; valor: number }[];
  pronostico: { fecha: string; valor: number; inferior: number; superior: number }[];
  total_pronosticado: number;
}

export type NivelAlerta = "rojo" | "amarillo" | "verde";

export interface Alerta {
  id: string;
  codigo: string;
  nivel: NivelAlerta;
  titulo: string;
  mensaje: string;
  accion: string;
  modulo: "resumen" | "finanzas" | "productos" | "flujo" | "proyecciones" | "impuestos" | "deudas";
  metricas: Record<string, string>;
  redactado_por_ia: boolean;
}

export interface ChatRespuesta {
  answer: string;
  intencion: string;
  periodo: Periodo;
  fuente: "ollama" | "plantilla";
  sugerencias: string[];
  datos: Record<string, unknown>;
}

export type TipoDatos = "ventas" | "productos" | "compras" | "gastos";

export interface CampoImport {
  clave: string;
  etiqueta: string;
  requerido: boolean;
  descripcion: string;
  ejemplo: string;
}

export interface Analisis {
  token: string;
  tipo_datos: TipoDatos;
  nombre_archivo: string;
  filas: number;
  fila_encabezado: number;
  columnas: { nombre: string; tipo_detectado: string; vacios: number; muestra: string[]; texto_en_numerica: boolean }[];
  mapeo: { columna: string; campo: string | null; fuente: "reglas" | "ia" | null }[];
  campos: CampoImport[];
  advertencias: string[];
  uso_ia: boolean;
  vista_previa: string[][];
}

export interface ErrorFila {
  fila: number;
  motivo: string;
}

export interface Previsualizacion {
  filas_ok: number;
  filas_con_error: number;
  errores: ErrorFila[];
  advertencias: string[];
  muestra: Record<string, string>[];
}

export interface ReporteCarga {
  id_importacion: number;
  estado: "completada" | "con_errores";
  filas_ok: number;
  filas_con_error: number;
  errores: ErrorFila[];
  advertencias: string[];
  productos_creados: string[];
  productos_actualizados: number;
}

export interface Importacion {
  id_importacion: number;
  nombre_archivo: string;
  tipo_datos: TipoDatos;
  fecha: string;
  estado: "completada" | "con_errores" | "deshecha";
  filas_ok: number;
  filas_con_error: number;
  errores: ErrorFila[];
}
