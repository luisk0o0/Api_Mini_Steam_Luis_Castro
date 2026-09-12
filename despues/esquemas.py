"""Esquemas de entrada de la API ."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProductoEntrada(BaseModel):
    tipo: str = Field(..., description="juego | dlc")
    nombre: str
    precio_base: float = Field(..., ge=0)
    etiquetas: List[str] = []
    juego_base_id: Optional[int] = None
    peso_gb: Optional[float] = None


class CheckoutEntrada(BaseModel):
    metodo_pago: str = Field(..., description="tarjeta | paypal | saldo | cripto")
    datos: Dict[str, Any] = {}
