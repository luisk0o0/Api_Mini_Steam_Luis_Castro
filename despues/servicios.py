"""Casos de uso. Aqui se orquestan los cinco patrones, sin saber nada de HTTP.

Cada servicio recibe sus colaboradores por constructor (inyeccion de
dependencias), asi que en las pruebas se pueden sustituir por dobles. Esa es la
diferencia de fondo con `antes/tienda.py`, donde la clase se construia a si
misma todas sus dependencias.
"""

import datetime

from despues.errores import CarritoVacio, ProductoNoEncontrado, ReglaDeNegocio
from despues.eventos import CompraRealizada, sujeto_por_defecto
from despues.factories import TipoProductoNoSoportado, obtener_fabrica
from despues.pagos import PagoRechazado, obtener_estrategia
from despues.precios import PoliticaPrecios
from despues.repositorios import (RepositorioBiblioteca, RepositorioCarrito,
                                  RepositorioCompras, RepositorioProductos)


class ServicioCatalogo:

    def __init__(self, productos=None, biblioteca=None, politica=None):
        self.productos = productos or RepositorioProductos()
        self.biblioteca = biblioteca or RepositorioBiblioteca()
        self.politica = politica or PoliticaPrecios()

    def _con_precio(self, producto, fecha):
        precio = self.politica.calcular(
            producto, fecha,
            posee_juego_base=self.biblioteca.posee(producto.juego_base_id))
        datos = producto.a_dict()
        datos.update(precio.a_dict())
        return datos

    def listar(self, fecha=None):
        return [self._con_precio(p, fecha) for p in self.productos.todos()]

    def detalle(self, producto_id, fecha=None):
        producto = self.productos.por_id(producto_id)
        if producto is None:
            raise ProductoNoEncontrado("Producto #%s no encontrado" % producto_id)
        return self._con_precio(producto, fecha)

    def crear(self, datos):
        """Unico punto de alta: elige la fabrica y deja que ella construya."""
        try:
            fabrica = obtener_fabrica(datos.get("tipo"))
        except TipoProductoNoSoportado as error:
            raise ReglaDeNegocio(str(error))
        try:
            producto = fabrica.registrar(datos)
        except ValueError as error:
            raise ReglaDeNegocio(str(error))
        return self.productos.guardar(producto)


class ServicioCarrito:

    def __init__(self, carrito=None, productos=None, biblioteca=None, politica=None):
        self.carrito = carrito or RepositorioCarrito()
        self.productos = productos or RepositorioProductos()
        self.biblioteca = biblioteca or RepositorioBiblioteca()
        self.politica = politica or PoliticaPrecios()

    def agregar(self, producto_id):
        if not self.productos.existe(producto_id):
            raise ProductoNoEncontrado("Producto #%s no encontrado" % producto_id)
        if self.biblioteca.posee(producto_id):
            raise ReglaDeNegocio("Ya tienes ese producto en tu biblioteca")
        self.carrito.agregar(producto_id)

    def quitar(self, producto_id):
        if not self.carrito.quitar(producto_id):
            raise ProductoNoEncontrado("Ese producto no esta en el carrito")

    def calcular_items(self, fecha=None):
        """Devuelve [(producto, PrecioCalculado)] con la MISMA cadena que /games."""
        resultado = []
        for producto in self.carrito.items():
            precio = self.politica.calcular(
                producto, fecha,
                posee_juego_base=self.biblioteca.posee(producto.juego_base_id))
            resultado.append((producto, precio))
        return resultado

    def ver(self, fecha=None):
        items = self.calcular_items(fecha)
        detalle = []
        for producto, precio in items:
            datos = producto.a_dict()
            datos.update(precio.a_dict())
            detalle.append(datos)
        subtotal = round(sum(p.precio_final for _, p in items), 2)
        ahorro = round(sum(p.ahorro for _, p in items), 2)
        return {"items": detalle, "subtotal": subtotal, "ahorro_total": ahorro}


class ServicioCheckout:
    """Context del Strategy y publicador del Observer.

    Su unica responsabilidad es coordinar: cobrar y anunciar. Ni entrega
    productos ni envia correos; de eso se encargan los observadores.
    """

    def __init__(self, carrito=None, compras=None, sujeto=None, usuario_id=None):
        self.servicio_carrito = carrito or ServicioCarrito()
        self.compras = compras or RepositorioCompras()
        self.sujeto = sujeto if sujeto is not None else sujeto_por_defecto()
        self.usuario_id = usuario_id or self.compras.usuario_id

    def procesar(self, metodo_pago, datos_pago=None, fecha=None):
        fecha = fecha or datetime.date.today()
        items = self.servicio_carrito.calcular_items(fecha)
        if not items:
            raise CarritoVacio("El carrito esta vacio")

        estrategia = obtener_estrategia(metodo_pago)          # Strategy
        total = round(sum(precio.precio_final for _, precio in items), 2)

        resultado = estrategia.cobrar(total, datos_pago or {})
        if not resultado.exitoso:
            raise PagoRechazado(resultado.mensaje)

        self.compras.registrar(total, metodo_pago, resultado.referencia, fecha)

        evento = CompraRealizada(                              # Observer
            usuario_id=self.usuario_id,
            items=[(producto, precio.precio_final) for producto, precio in items],
            total=total,
            metodo_pago=metodo_pago,
            referencia=resultado.referencia,
            fecha=fecha,
        )
        self.sujeto.notificar(evento)
        self.servicio_carrito.carrito.vaciar()

        return {
            "referencia": resultado.referencia,
            "total": total,
            "metodo_pago": metodo_pago,
            "mensaje": resultado.mensaje,
            "productos": [p.nombre for p in evento.productos],
        }


class ServicioBiblioteca:

    def __init__(self, biblioteca=None):
        self.biblioteca = biblioteca or RepositorioBiblioteca()

    def listar(self):
        return self.biblioteca.listar()
