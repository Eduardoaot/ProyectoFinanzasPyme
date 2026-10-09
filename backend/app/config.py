"""Configuración de la aplicación, leída de variables de entorno (archivo .env)."""

from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class UmbralesAlerta(BaseModel):
    """Umbrales por defecto de las alertas. Cada empresa puede sobrescribirlos."""

    margen_neto_bajo: float = 0.20          # 🔴 margen de la empresa por debajo de esto
    margen_producto_bajo: float = 0.10      # 🔴 margen de un producto por debajo de esto
    dias_inventario_bajo: float = 3         # 🔴 días de inventario restantes (🟡 hasta el doble)
    gastos_vs_ventas_pp: float = 0.05       # 🟡 gastos crecen 5 pp más que las ventas
    caida_ventas: float = 0.10              # 🟡 ventas caen 10% vs mes anterior
    subida_costo: float = 0.05              # 🟡 costo sube 5% y el precio no
    buena_rentabilidad: float = 0.30        # 🟢 margen por encima de esto
    crecimiento_ventas: float = 0.05        # 🟢 ventas crecen 5% vs mes anterior


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "mysql+pymysql://root:@localhost:3306/cuentas_claras?charset=utf8mb4"
    jwt_secret: str = "cambia-esto-en-produccion"
    jwt_expira_horas: int = 12

    ollama_url: str = "http://127.0.0.1:11434"   # 127.0.0.1 evita ~2 s de resolución IPv6 en Windows
    ollama_modelo: str = "llama3.2:3b"
    ollama_timeout: float = 120.0
    ollama_keep_alive: str = "30m"              # cuánto tiempo sigue cargado el modelo sin uso (Ollama trae 5m)

    cors_origenes: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_archivo_mb: int = 5
    carpeta_staging: str = ".staging"

    umbrales: UmbralesAlerta = UmbralesAlerta()


@lru_cache
def get_settings() -> Settings:
    return Settings()
