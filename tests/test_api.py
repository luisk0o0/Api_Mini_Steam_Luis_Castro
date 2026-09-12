"""Pruebas de los 8 endpoints con el cliente de pruebas de FastAPI.

Requieren `pip install -r requirements.txt`. Las pruebas de dominio
(`test_dominio.py`) corren aunque no haya servidor.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from despues import main
from despues.db import BaseDatos

INVIERNO = "2026-12-25"
HALLOWEEN = "2026-10-31"
SIN_PROMO = "2026-03-15"
TARJETA = {"numero": "4111111111111111", "cvv": "123"}


@pytest.fixture()
def cliente():
    ruta = os.path.join(tempfile.mkdtemp(), "steam.db")
    base_datos = BaseDatos.reiniciar(ruta)
    base_datos.crear_esquema()
    base_datos.sembrar_datos()
    return TestClient(main.app)


def test_catalogo_aplica_la_promocion_vigente(cliente):
    respuesta = cliente.get("/games", params={"fecha": INVIERNO})
    assert respuesta.status_code == 200
    catalogo = respuesta.json()
    assert len(catalogo) == 5
    assert catalogo[0]["promocion"] == "Rebajas de Invierno"
    assert catalogo[0]["precio_final"] == 99960.0


def test_catalogo_sin_promocion_solo_suma_iva(cliente):
    catalogo = cliente.get("/games", params={"fecha": SIN_PROMO}).json()
    assert catalogo[0]["promocion"] is None
    assert catalogo[0]["precio_final"] == round(120000 * 1.19, 2)


def test_detalle_y_404(cliente):
    assert cliente.get("/games/1", params={"fecha": SIN_PROMO}).status_code == 200
    assert cliente.get("/games/9999").status_code == 404


def test_crear_juego_y_dlc(cliente):
    nuevo = cliente.post("/games", json={
        "tipo": "juego", "nombre": "Neon Drift", "precio_base": 75000,
        "etiquetas": ["carreras"], "peso_gb": 20})
    assert nuevo.status_code == 201
    id_nuevo = nuevo.json()["id"]

    dlc = cliente.post("/games", json={
        "tipo": "dlc", "nombre": "Neon Drift: Circuitos", "precio_base": 20000,
        "juego_base_id": id_nuevo})
    assert dlc.status_code == 201
    assert dlc.json()["juego_base_id"] == id_nuevo


def test_crear_producto_invalido(cliente):
    sin_peso = cliente.post("/games", json={
        "tipo": "juego", "nombre": "X", "precio_base": 1000})
    assert sin_peso.status_code == 400

    tipo_raro = cliente.post("/games", json={
        "tipo": "bundle", "nombre": "X", "precio_base": 1000})
    assert tipo_raro.status_code == 400

    dlc_huerfano = cliente.post("/games", json={
        "tipo": "dlc", "nombre": "X", "precio_base": 1000, "juego_base_id": 9999})
    assert dlc_huerfano.status_code == 400


def test_carrito_agregar_y_quitar(cliente):
    assert cliente.post("/cart/1").status_code == 200
    assert cliente.post("/cart/2").status_code == 200
    carrito = cliente.get("/cart", params={"fecha": INVIERNO}).json()
    assert len(carrito["items"]) == 2

    assert cliente.delete("/cart/2").status_code == 200
    assert len(cliente.get("/cart").json()["items"]) == 1

    assert cliente.delete("/cart/2").status_code == 404
    assert cliente.post("/cart/9999").status_code == 404


def test_subtotal_del_carrito_es_lo_que_se_cobra(cliente):
    cliente.post("/cart/1")
    subtotal = cliente.get("/cart", params={"fecha": INVIERNO}).json()["subtotal"]
    compra = cliente.post("/checkout", json={"metodo_pago": "tarjeta", "datos": TARJETA},
                          params={"fecha": INVIERNO})
    assert compra.status_code == 200
    assert compra.json()["total"] == subtotal == 99960.0


def test_checkout_llena_la_biblioteca_y_vacia_el_carrito(cliente):
    cliente.post("/cart/1")
    cliente.post("/cart/4")
    compra = cliente.post("/checkout",
                          json={"metodo_pago": "paypal", "datos": {"correo": "yo@x.com"}},
                          params={"fecha": SIN_PROMO})
    assert compra.status_code == 200
    assert compra.json()["referencia"].startswith("PP-")

    biblioteca = cliente.get("/library").json()
    assert sorted(item["id"] for item in biblioteca) == [1, 4]
    assert cliente.get("/cart").json()["items"] == []


def test_checkout_rechazado_no_entrega_nada(cliente):
    cliente.post("/cart/1")
    fallido = cliente.post("/checkout",
                           json={"metodo_pago": "tarjeta", "datos": {"numero": "123"}},
                           params={"fecha": SIN_PROMO})
    assert fallido.status_code == 400
    assert cliente.get("/library").json() == []
    assert len(cliente.get("/cart").json()["items"]) == 1


def test_checkout_con_carrito_vacio(cliente):
    respuesta = cliente.post("/checkout",
                             json={"metodo_pago": "tarjeta", "datos": TARJETA})
    assert respuesta.status_code == 400


def test_medio_de_pago_no_soportado(cliente):
    cliente.post("/cart/1")
    respuesta = cliente.post("/checkout", json={"metodo_pago": "trueque", "datos": {}})
    assert respuesta.status_code == 400


def test_no_se_recompra_lo_que_ya_esta_en_la_biblioteca(cliente):
    cliente.post("/cart/1")
    cliente.post("/checkout", json={"metodo_pago": "saldo", "datos": {}},
                 params={"fecha": INVIERNO})
    repetido = cliente.post("/cart/1")
    assert repetido.status_code == 400


def test_descuento_de_fidelidad_en_dlc(cliente):
    """Al comprar el juego base, su DLC baja de precio automaticamente."""
    antes = cliente.get("/games/4", params={"fecha": SIN_PROMO}).json()["precio_final"]
    cliente.post("/cart/1")
    cliente.post("/checkout", json={"metodo_pago": "saldo", "datos": {}},
                 params={"fecha": SIN_PROMO})
    despues = cliente.get("/games/4", params={"fecha": SIN_PROMO}).json()["precio_final"]
    assert despues < antes
    assert despues == 42840.0


def test_fecha_invalida(cliente):
    assert cliente.get("/games", params={"fecha": "25-12-2026"}).status_code == 400


def test_meta_lista_las_extensiones_registradas(cliente):
    meta = cliente.get("/meta").json()
    assert meta["tipos_de_producto"] == ["dlc", "juego"]
    assert meta["medios_de_pago"] == ["cripto", "paypal", "saldo", "tarjeta"]
