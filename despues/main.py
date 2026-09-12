"""Capa web: rutas delgadas.

Cada endpoint hace tres cosas: traducir la peticion, llamar a un servicio y
traducir el error de dominio a un codigo HTTP. Ninguna regla de negocio vive
aqui (comparar con `antes/main.py`, donde las rutas validaban DLCs y medios de
pago por su cuenta).
"""

import datetime
import logging

from fastapi import FastAPI, HTTPException

from despues.db import BaseDatos
from despues.errores import ProductoNoEncontrado, ReglaDeNegocio
from despues.esquemas import CheckoutEntrada, ProductoEntrada
from despues.factories import tipos_disponibles
from despues.pagos import PagoRechazado, medios_disponibles
from despues.servicios import (ServicioBiblioteca, ServicioCarrito,
                               ServicioCatalogo, ServicioCheckout)

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Mini-Steam (DESPUES)",
    description="Tienda de videojuegos refactorizada con 5 patrones GoF.",
)

_bd = BaseDatos.instancia()
_bd.crear_esquema()
_bd.sembrar_datos()


def _fecha(valor):
    """Permite simular la fecha para demostrar las rebajas estacionales."""
    if not valor:
        return None
    try:
        return datetime.date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha invalida, usa AAAA-MM-DD")


@app.get("/games")
def listar_juegos(fecha: str = None):
    return ServicioCatalogo().listar(_fecha(fecha))


@app.get("/games/{producto_id}")
def ver_juego(producto_id: int, fecha: str = None):
    try:
        return ServicioCatalogo().detalle(producto_id, _fecha(fecha))
    except ProductoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error))


def _a_dict(modelo):
    """Compatibilidad Pydantic v1 (.dict) / v2 (.model_dump)."""
    return modelo.model_dump() if hasattr(modelo, "model_dump") else modelo.dict()


@app.post("/games", status_code=201)
def crear_juego(entrada: ProductoEntrada):
    try:
        producto = ServicioCatalogo().crear(_a_dict(entrada))
    except ReglaDeNegocio as error:
        raise HTTPException(status_code=400, detail=str(error))
    return producto.a_dict()


@app.get("/cart")
def ver_carrito(fecha: str = None):
    return ServicioCarrito().ver(_fecha(fecha))


@app.post("/cart/{producto_id}")
def agregar_al_carrito(producto_id: int):
    servicio = ServicioCarrito()
    try:
        servicio.agregar(producto_id)
    except ProductoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ReglaDeNegocio as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"mensaje": "Producto agregado al carrito"}


@app.delete("/cart/{producto_id}")
def quitar_del_carrito(producto_id: int):
    try:
        ServicioCarrito().quitar(producto_id)
    except ProductoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error))
    return {"mensaje": "Producto retirado del carrito"}


@app.post("/checkout")
def checkout(entrada: CheckoutEntrada, fecha: str = None):
    try:
        return ServicioCheckout().procesar(entrada.metodo_pago, entrada.datos,
                                           _fecha(fecha))
    except (ReglaDeNegocio, PagoRechazado) as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/library")
def biblioteca():
    return ServicioBiblioteca().listar()


@app.get("/meta")
def meta():
    """Ayuda para la sustentacion: que extensiones estan registradas hoy."""
    return {
        "tipos_de_producto": tipos_disponibles(),
        "medios_de_pago": medios_disponibles(),
    }
