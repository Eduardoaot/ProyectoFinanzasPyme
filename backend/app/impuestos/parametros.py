"""Carga de los parámetros fiscales por año de vigencia (parametros_fiscales.json).

Nada de tasas ni tarifas vive en la lógica: se actualizan agregando un año al JSON.
"""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

RUTA = Path(__file__).with_name("parametros_fiscales.json")


@lru_cache
def _todos() -> dict[int, dict]:
    crudo = json.loads(RUTA.read_text(encoding="utf-8"))
    return {int(anio): datos for anio, datos in crudo.items() if anio.isdigit()}


def parametros(anio: int) -> dict:
    """Parámetros del año; si no existe, el más reciente que no sea posterior (o el primero disponible)."""
    todos = _todos()
    if anio in todos:
        return {**todos[anio], "anio": anio}
    anteriores = [a for a in todos if a <= anio]
    vigente = max(anteriores) if anteriores else min(todos)
    return {**todos[vigente], "anio": vigente}


def sin_acentos(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _litros(nombre: str) -> float | None:
    """Litros que dice el nombre ("Agua 20 L" → 20); None si no trae presentación."""
    hallado = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:l|lt|lts|litros?)\b", nombre)
    return float(hallado.group(1).replace(",", ".")) if hallado else None


def tasa_iva_sugerida(categoria: str, nombre: str, anio: int) -> float:
    """0 % para alimentos (y agua en garrafón); 16 % para bebidas, agua chica y lo demás. El usuario puede corregirla por producto."""
    p = parametros(anio)["iva"]
    cat, nom = sin_acentos(categoria), sin_acentos(nombre)
    if any(clave in nom for clave in p["excepciones_tasa_cero_por_nombre"]):
        return p["tasa_cero"]
    litros = _litros(nom)
    if "agua" in nom and litros is not None and litros >= p["agua_tasa_cero_litros_minimos"]:
        return p["tasa_cero"]
    if any(clave in nom for clave in p["excepciones_tasa_general_por_nombre"]):
        return p["tasa_general"]
    if cat in p["categorias_tasa_general"]:
        return p["tasa_general"]
    if cat in p["categorias_tasa_cero"]:
        return p["tasa_cero"]
    return p["tasa_general"]
