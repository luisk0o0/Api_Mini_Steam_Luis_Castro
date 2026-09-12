"""Version ANTES: la capa web tambien participa del desorden.

Cada endpoint construye su propia `TiendaSteam` (y por lo tanto su propia
conexion), y ademas mete reglas de negocio dentro de la ruta HTTP.
"""

import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from antes.tienda import TiendaSteam

app = FastAPI(title="Mini-Steam (ANTES)")

TiendaSteam().crear_esquema()


class ProductoEntrada(BaseModel):
    tipo: str
    nombre: str
    precio_base: float
    etiquetas: list = []
    juego_base_id: int = None
    peso_gb: float = None


class CheckoutEntrada(BaseModel):
    metodo_pago: str
    datos: dict = {}


def _fecha(valor):
    if not valor:
        return None
    try:
        return datetime.date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha invalida, usa AAAA-MM-DD")


@app.get("/games")
def listar_juegos(fecha: str = None):
    tienda = TiendaSteam()
    return tienda.catalogo(_fecha(fecha))


@app.get("/games/{producto_id}")
def ver_juego(producto_id: int, fecha: str = None):
    tienda = TiendaSteam()
    datos = tienda.detalle(producto_id, _fecha(fecha))
    if datos is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return datos


@app.post("/games", status_code=201)
def crear_juego(entrada: ProductoEntrada):
    tienda = TiendaSteam()
    # regla de negocio metida en la ruta HTTP
    if entrada.tipo == "dlc" and entrada.juego_base_id is None:
        raise HTTPException(status_code=400, detail="Un DLC necesita juego_base_id")
    if entrada.tipo == "juego" and entrada.peso_gb is None:
        raise HTTPException(status_code=400, detail="Un juego necesita peso_gb")
    try:
        producto = tienda.crear_producto(
            entrada.model_dump() if hasattr(entrada, "model_dump") else entrada.dict())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return producto.a_dict()


@app.get("/cart")
def ver_carrito(fecha: str = None):
    tienda = TiendaSteam()
    return tienda.ver_carrito(_fecha(fecha))


@app.post("/cart/{producto_id}")
def agregar_carrito(producto_id: int):
    tienda = TiendaSteam()
    try:
        tienda.agregar_al_carrito(producto_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"mensaje": "Producto agregado al carrito"}


@app.delete("/cart/{producto_id}")
def quitar_carrito(producto_id: int):
    tienda = TiendaSteam()
    try:
        tienda.quitar_del_carrito(producto_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    return {"mensaje": "Producto retirado del carrito"}


@app.post("/checkout")
def checkout(entrada: CheckoutEntrada, fecha: str = None):
    tienda = TiendaSteam()
    if entrada.metodo_pago not in ("tarjeta", "paypal", "saldo", "cripto"):
        raise HTTPException(status_code=400, detail="Medio de pago no soportado")
    try:
        return tienda.checkout(entrada.metodo_pago, entrada.datos, _fecha(fecha))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/library")
def biblioteca():
    tienda = TiendaSteam()
    return tienda.biblioteca()
