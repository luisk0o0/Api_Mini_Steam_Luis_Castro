"""Pruebas del dominio: una seccion por patron, sin levantar el servidor.

Se escriben como funciones planas (sin fixtures) para que corran igual con
`pytest` que con `python -m tests.correr_pruebas`.
"""

import datetime
import os
import tempfile

from despues.db import BaseDatos
from despues.errores import CarritoVacio, ProductoNoEncontrado, ReglaDeNegocio
from despues.eventos import (CompraRealizada, ObservadorBiblioteca,
                             ObservadorCompra, SujetoCompra, sujeto_por_defecto)
from despues.factories import (FabricaDLC, TipoProductoNoSoportado,
                               obtener_fabrica, tipos_disponibles)
from despues.modelos import DLC, Juego
from despues.pagos import (PagoRechazado, PagoSaldo, obtener_estrategia,
                           medios_disponibles)
from despues.precios import (CalendarioPromociones, DescuentoEstacional,
                             ImpuestoIVA, PoliticaPrecios, PrecioBase,
                             Promocion)
from despues.servicios import (ServicioBiblioteca, ServicioCarrito,
                               ServicioCatalogo, ServicioCheckout)

INVIERNO = datetime.date(2026, 12, 25)
HALLOWEEN = datetime.date(2026, 10, 31)
SIN_PROMO = datetime.date(2026, 3, 15)

TARJETA = {"numero": "4111111111111111", "cvv": "123"}


def preparar():
    """Base de datos limpia en un archivo temporal."""
    ruta = os.path.join(tempfile.mkdtemp(), "steam.db")
    bd = BaseDatos.reiniciar(ruta)
    bd.crear_esquema()
    bd.sembrar_datos()
    return bd


# ----------------------------------------------------------------------
# Patron 1: Singleton
# ----------------------------------------------------------------------
def test_singleton_devuelve_siempre_la_misma_instancia():
    preparar()
    assert BaseDatos() is BaseDatos.instancia()
    assert BaseDatos().conexion is BaseDatos.instancia().conexion


def test_singleton_no_reinicializa_la_conexion():
    bd = preparar()
    conexion_original = bd.conexion
    otra = BaseDatos("/ruta/que/nunca/se/usa.db")
    assert otra is bd
    assert otra.conexion is conexion_original


def test_una_escritura_se_ve_desde_cualquier_referencia():
    preparar()
    BaseDatos().ejecutar("INSERT INTO carrito (usuario_id, producto_id) VALUES (1, 1)")
    fila = BaseDatos.instancia().consultar_uno("SELECT COUNT(*) AS n FROM carrito")
    assert fila["n"] == 1


# ----------------------------------------------------------------------
# Patron 2: Factory Method
# ----------------------------------------------------------------------
def test_fabrica_construye_el_tipo_correcto():
    preparar()
    juego = obtener_fabrica("juego").registrar(
        {"nombre": "Test", "precio_base": 1000, "peso_gb": 5, "etiquetas": []})
    assert isinstance(juego, Juego)
    assert juego.tipo == "juego"
    assert juego.juego_base_id is None


def test_fabrica_dlc_exige_juego_base_existente():
    preparar()
    fabrica = obtener_fabrica("dlc")
    dlc = fabrica.registrar(
        {"nombre": "Expansion", "precio_base": 1000, "juego_base_id": 1})
    assert isinstance(dlc, DLC)
    try:
        fabrica.registrar(
            {"nombre": "Huerfano", "precio_base": 1000, "juego_base_id": 9999})
        raise AssertionError("Debio rechazar un DLC sin juego base")
    except ValueError:
        pass


def test_tipo_desconocido_no_rompe_el_sistema():
    preparar()
    try:
        obtener_fabrica("bundle")
        raise AssertionError("Debio lanzar TipoProductoNoSoportado")
    except TipoProductoNoSoportado as error:
        assert "bundle" in str(error)
    assert tipos_disponibles() == ["dlc", "juego"]


def test_fabrica_dlc_acepta_una_comprobacion_inyectada():
    """Sin base de datos: la fabrica no depende de SQLite."""
    fabrica = FabricaDLC(existe_producto=lambda _id: True)
    dlc = fabrica.registrar({"nombre": "X", "precio_base": 100, "juego_base_id": 42})
    assert dlc.juego_base_id == 42


# ----------------------------------------------------------------------
# Patron 3: Decorator
# ----------------------------------------------------------------------
def test_cadena_de_decoradores_se_aplica_en_orden():
    juego = Juego("Hollow Depths", 120000, peso_gb=12.5)
    promocion = Promocion("Rebajas de Invierno", 0.30, (12, 22), (1, 5))
    componente = ImpuestoIVA(DescuentoEstacional(PrecioBase(juego), promocion))
    # 120000 * 0.70 = 84000 ; 84000 * 1.19 = 99960
    assert round(componente.calcular(), 2) == 99960.0
    conceptos = [paso["concepto"] for paso in componente.desglose()]
    assert conceptos == ["Precio base", "Rebajas de Invierno", "IVA 19%"]


def test_promociones_son_excluyentes():
    calendario = CalendarioPromociones()
    juego = Juego("Silent Manor", 90000, peso_gb=30, etiquetas=["terror"])
    vigente = calendario.vigente(juego, HALLOWEEN)
    assert vigente is not None and vigente.nombre == "Halloween"
    # Solo una promocion puede estar vigente a la vez
    activas = [p for p in calendario.promociones if p.vigente_en(HALLOWEEN)]
    assert len(activas) == 1


def test_promocion_por_etiqueta_no_alcanza_a_todos():
    calendario = CalendarioPromociones()
    generico = Juego("Galactic Freight", 160000, peso_gb=45, etiquetas=["espacio"])
    assert calendario.vigente(generico, HALLOWEEN) is None
    politica = PoliticaPrecios()
    assert politica.calcular(generico, HALLOWEEN).precio_final == 190400.0


def test_temporada_que_cruza_el_ano_nuevo():
    promocion = Promocion("Invierno", 0.30, (12, 22), (1, 5))
    assert promocion.vigente_en(datetime.date(2026, 12, 31))
    assert promocion.vigente_en(datetime.date(2027, 1, 3))
    assert not promocion.vigente_en(datetime.date(2027, 1, 6))


def test_decorador_extra_de_fidelidad_se_apila():
    dlc = DLC("Abismo", 40000, juego_base_id=1)
    politica = PoliticaPrecios()
    sin_juego = politica.calcular(dlc, SIN_PROMO, posee_juego_base=False)
    con_juego = politica.calcular(dlc, SIN_PROMO, posee_juego_base=True)
    assert sin_juego.precio_final == 47600.0    # 40000 * 1.19
    assert con_juego.precio_final == 42840.0    # 40000 * 0.9 * 1.19
    assert con_juego.ahorro > sin_juego.ahorro


# ----------------------------------------------------------------------
# Patron 4: Strategy
# ----------------------------------------------------------------------
def test_cada_estrategia_valida_lo_suyo():
    preparar()
    assert obtener_estrategia("tarjeta").cobrar(1000, TARJETA).exitoso
    assert not obtener_estrategia("tarjeta").cobrar(1000, {"numero": "123"}).exitoso
    assert obtener_estrategia("paypal").cobrar(1000, {"correo": "a@b.com"}).exitoso
    assert not obtener_estrategia("paypal").cobrar(1000, {"correo": "nope"}).exitoso
    assert obtener_estrategia("cripto").cobrar(1000, {"wallet": "0xabc"}).exitoso
    assert not obtener_estrategia("cripto").cobrar(1000, {"wallet": "abc"}).exitoso


def test_saldo_insuficiente_es_rechazo_no_excepcion():
    preparar()
    resultado = PagoSaldo().cobrar(999999999, {})
    assert not resultado.exitoso
    assert "insuficiente" in resultado.mensaje


def test_saldo_descuenta_la_billetera():
    bd = preparar()
    PagoSaldo().cobrar(50000, {})
    fila = bd.consultar_uno("SELECT saldo FROM billetera WHERE usuario_id = 1")
    assert fila["saldo"] == 150000.0


def test_medio_de_pago_desconocido():
    preparar()
    try:
        obtener_estrategia("trueque")
        raise AssertionError("Debio lanzar PagoRechazado")
    except PagoRechazado as error:
        assert "trueque" in str(error)
    assert medios_disponibles() == ["cripto", "paypal", "saldo", "tarjeta"]


# ----------------------------------------------------------------------
# Patron 5: Observer
# ----------------------------------------------------------------------
def _evento_de_prueba():
    juego = Juego("Hollow Depths", 120000, peso_gb=12.5, id=1)
    return CompraRealizada(usuario_id=1, items=[(juego, 99960.0)], total=99960.0,
                           metodo_pago="tarjeta", referencia="TARJ-000001",
                           fecha=INVIERNO)


def test_los_tres_observadores_reaccionan_al_evento():
    bd = preparar()
    sujeto_por_defecto().notificar(_evento_de_prueba())
    assert bd.consultar_uno("SELECT COUNT(*) AS n FROM biblioteca")["n"] == 1
    assert bd.consultar_uno("SELECT COUNT(*) AS n FROM notificaciones")["n"] == 1
    assert bd.consultar_uno("SELECT ventas FROM estadisticas WHERE producto_id=1")["ventas"] == 1


def test_se_pueden_agregar_y_quitar_observadores_en_caliente():
    preparar()
    recibidos = []

    class Espia(ObservadorCompra):
        def actualizar(self, evento):
            recibidos.append(evento.referencia)

    sujeto = SujetoCompra()
    espia = Espia()
    sujeto.suscribir(espia)
    sujeto.notificar(_evento_de_prueba())
    sujeto.desuscribir(espia)
    sujeto.notificar(_evento_de_prueba())
    assert recibidos == ["TARJ-000001"]


def test_un_observador_no_critico_que_falla_no_tumba_la_compra():
    bd = preparar()

    class Roto(ObservadorCompra):
        def actualizar(self, evento):
            raise RuntimeError("el servidor de correo se cayo")

    sujeto = SujetoCompra()
    sujeto.suscribir(Roto())
    sujeto.suscribir(ObservadorBiblioteca())
    sujeto.notificar(_evento_de_prueba())
    assert bd.consultar_uno("SELECT COUNT(*) AS n FROM biblioteca")["n"] == 1


# ----------------------------------------------------------------------
# Integracion de los servicios
# ----------------------------------------------------------------------
def test_flujo_completo_carrito_checkout_biblioteca():
    preparar()
    carrito = ServicioCarrito()
    carrito.agregar(1)
    carrito.agregar(2)
    vista = carrito.ver(INVIERNO)
    assert len(vista["items"]) == 2

    resultado = ServicioCheckout().procesar("tarjeta", TARJETA, INVIERNO)
    assert resultado["total"] == vista["subtotal"]
    assert resultado["referencia"].startswith("TARJ-")

    biblioteca = ServicioBiblioteca().listar()
    assert [item["id"] for item in biblioteca] == [1, 2]
    assert ServicioCarrito().ver(INVIERNO)["items"] == []


def test_el_subtotal_del_carrito_coincide_con_el_cobro():
    """Regresion del defecto de la version ANTES (el carrito olvidaba el IVA)."""
    preparar()
    ServicioCarrito().agregar(1)
    subtotal = ServicioCarrito().ver(INVIERNO)["subtotal"]
    cobrado = ServicioCheckout().procesar("tarjeta", TARJETA, INVIERNO)["total"]
    assert subtotal == cobrado == 99960.0


def test_el_catalogo_y_el_carrito_dan_el_mismo_precio():
    preparar()
    del_catalogo = ServicioCatalogo().detalle(2, HALLOWEEN)["precio_final"]
    ServicioCarrito().agregar(2)
    del_carrito = ServicioCarrito().ver(HALLOWEEN)["items"][0]["precio_final"]
    assert del_catalogo == del_carrito == 64260.0   # 90000 * 0.6 * 1.19


def test_checkout_con_carrito_vacio():
    preparar()
    try:
        ServicioCheckout().procesar("tarjeta", TARJETA, SIN_PROMO)
        raise AssertionError("Debio lanzar CarritoVacio")
    except CarritoVacio:
        pass


def test_pago_rechazado_no_entrega_productos():
    bd = preparar()
    ServicioCarrito().agregar(3)
    try:
        ServicioCheckout().procesar("saldo", {}, SIN_PROMO)   # cuesta 190400 > 200000? no
        cobro_ok = True
    except PagoRechazado:
        cobro_ok = False
    # Galactic Freight con IVA cuesta 190400 y el saldo inicial es 200000
    assert cobro_ok
    # Ahora el saldo ya no alcanza para otra compra
    ServicioCarrito().agregar(1)
    try:
        ServicioCheckout().procesar("saldo", {}, SIN_PROMO)
        raise AssertionError("Debio rechazar por saldo insuficiente")
    except PagoRechazado:
        pass
    assert bd.consultar_uno("SELECT COUNT(*) AS n FROM biblioteca")["n"] == 1
    assert bd.consultar_uno("SELECT COUNT(*) AS n FROM carrito")["n"] == 1


def test_no_se_puede_comprar_dos_veces_lo_mismo():
    preparar()
    ServicioCarrito().agregar(1)
    ServicioCheckout().procesar("paypal", {"correo": "yo@correo.com"}, SIN_PROMO)
    try:
        ServicioCarrito().agregar(1)
        raise AssertionError("Debio rechazar un producto ya comprado")
    except ReglaDeNegocio:
        pass


def test_alta_de_producto_por_el_servicio():
    preparar()
    producto = ServicioCatalogo().crear(
        {"tipo": "juego", "nombre": "Nuevo", "precio_base": 50000, "peso_gb": 8})
    assert producto.id is not None
    assert ServicioCatalogo().detalle(producto.id, SIN_PROMO)["nombre"] == "Nuevo"
    try:
        ServicioCatalogo().crear({"tipo": "bundle", "nombre": "X", "precio_base": 1})
        raise AssertionError("Debio rechazar el tipo desconocido")
    except ReglaDeNegocio:
        pass


def test_producto_inexistente():
    preparar()
    try:
        ServicioCatalogo().detalle(9999, SIN_PROMO)
        raise AssertionError("Debio lanzar ProductoNoEncontrado")
    except ProductoNoEncontrado:
        pass
