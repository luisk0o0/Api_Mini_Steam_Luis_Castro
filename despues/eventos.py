"""PATRON 5 - OBSERVER (comportamiento).

Problema que resuelve: en `antes/tienda.py` el metodo `checkout()` hacia ocho
cosas seguidas: calcular, cobrar, registrar la compra, llenar la biblioteca,
actualizar estadisticas, vaciar el carrito, imprimir el correo y auditar.
Cualquier efecto secundario nuevo (logros, cupon de bienvenida, webhook)
significaba alargar ese metodo (viola SRP y OCP), y el envio de correo estaba
escrito con un `print` dentro de la logica de negocio (viola DIP).

Aqui el checkout solo publica un hecho: "se realizo una compra". Quien quiera
reaccionar se suscribe. La biblioteca (`GET /library`) se llena porque un
observador escucha ese evento.

Roles GoF:
    Subject          -> SujetoCompra
    Observer         -> ObservadorCompra
    ConcreteObserver -> ObservadorBiblioteca, ObservadorCorreo,
                        ObservadorEstadisticas
"""

import datetime
import logging
from abc import ABC, abstractmethod

from despues.db import BaseDatos

logger = logging.getLogger("mini-steam")


class CompraRealizada:
    """El evento que viaja del sujeto a los observadores."""

    def __init__(self, usuario_id, items, total, metodo_pago, referencia, fecha=None):
        self.usuario_id = usuario_id
        self.items = items                  # lista de (Producto, precio_pagado)
        self.total = total
        self.metodo_pago = metodo_pago
        self.referencia = referencia
        self.fecha = fecha or datetime.date.today()

    @property
    def productos(self):
        return [producto for producto, _ in self.items]


class ObservadorCompra(ABC):
    """Observer."""

    #: si un observador critico falla, la compra falla; los demas solo se loguean
    critico = False

    @abstractmethod
    def actualizar(self, evento):
        """Reacciona a una compra."""


class SujetoCompra:
    """Subject: mantiene la lista de suscriptores y los notifica."""

    def __init__(self):
        self._observadores = []

    def suscribir(self, observador):
        if observador not in self._observadores:
            self._observadores.append(observador)
        return observador

    def desuscribir(self, observador):
        if observador in self._observadores:
            self._observadores.remove(observador)

    @property
    def observadores(self):
        return list(self._observadores)

    def notificar(self, evento):
        """Notifica en orden de suscripcion.

        Un observador no critico que falle no puede tumbar la compra: su error
        se registra y se sigue. Un observador critico (la biblioteca) si
        propaga, porque sin el la compra quedaria cobrada pero sin entregar.
        """
        for observador in self._observadores:
            try:
                observador.actualizar(evento)
            except Exception as error:
                if observador.critico:
                    raise
                logger.warning("Observador %s fallo: %s",
                               type(observador).__name__, error)


class ObservadorBiblioteca(ObservadorCompra):
    """Entrega los productos comprados. Alimenta GET /library."""

    critico = True

    def __init__(self, base_datos=None):
        self.base_datos = base_datos or BaseDatos.instancia()

    def actualizar(self, evento):
        with self.base_datos.transaccion() as con:
            for producto, precio in evento.items:
                con.execute(
                    "INSERT OR IGNORE INTO biblioteca"
                    " (usuario_id, producto_id, fecha, precio_pagado)"
                    " VALUES (?,?,?,?)",
                    (evento.usuario_id, producto.id, evento.fecha.isoformat(), precio))


class ObservadorCorreo(ObservadorCompra):
    """Envio de correo SIMULADO: se guarda en tabla y se escribe al log."""

    def __init__(self, base_datos=None):
        self.base_datos = base_datos or BaseDatos.instancia()

    def actualizar(self, evento):
        asunto = "Confirmacion de compra %s" % evento.referencia
        cuerpo = "Gracias por tu compra de %d producto(s) por $%.2f: %s" % (
            len(evento.items), evento.total,
            ", ".join(p.nombre for p in evento.productos))
        self.base_datos.ejecutar(
            "INSERT INTO notificaciones (usuario_id, asunto, cuerpo, fecha)"
            " VALUES (?,?,?,?)",
            (evento.usuario_id, asunto, cuerpo, evento.fecha.isoformat()))
        logger.info("[CORREO SIMULADO] %s -> %s", asunto, cuerpo)


class ObservadorEstadisticas(ObservadorCompra):
    """Lleva la cuenta de unidades vendidas por producto."""

    def __init__(self, base_datos=None):
        self.base_datos = base_datos or BaseDatos.instancia()

    def actualizar(self, evento):
        with self.base_datos.transaccion() as con:
            for producto, _precio in evento.items:
                con.execute(
                    "INSERT INTO estadisticas (producto_id, ventas) VALUES (?, 1)"
                    " ON CONFLICT(producto_id) DO UPDATE SET ventas = ventas + 1",
                    (producto.id,))


def sujeto_por_defecto(base_datos=None):
    """Arma el sujeto con los tres observadores estandar."""
    sujeto = SujetoCompra()
    sujeto.suscribir(ObservadorBiblioteca(base_datos))
    sujeto.suscribir(ObservadorCorreo(base_datos))
    sujeto.suscribir(ObservadorEstadisticas(base_datos))
    return sujeto
