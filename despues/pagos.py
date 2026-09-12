"""PATRON 4 - STRATEGY (comportamiento).

Problema que resuelve: en `antes/tienda.py`, `procesar_pago()` era un if/elif
con la validacion y el cobro de los cuatro medios de pago mezclados en el mismo
metodo. Agregar "Nequi" o "PSE" obligaba a modificar ese metodo (viola OCP) y
un error en la rama de cripto podia romper la de tarjeta (viola SRP).

Aqui cada medio de pago es una clase con la misma interfaz. El servicio de
checkout no sabe cual esta usando: recibe una estrategia y la ejecuta.

Roles GoF:
    Strategy         -> EstrategiaPago
    ConcreteStrategy -> PagoTarjeta, PagoPayPal, PagoSaldo, PagoCripto
    Context          -> ServicioCheckout (en servicios.py), que recibe la
                        estrategia por constructor/parametro.

"""

import random
from abc import ABC, abstractmethod

from despues.db import BaseDatos
from despues.modelos import USUARIO_ID


class ResultadoPago:

    def __init__(self, exitoso, referencia=None, mensaje=""):
        self.exitoso = exitoso
        self.referencia = referencia
        self.mensaje = mensaje

    def a_dict(self):
        return {"exitoso": self.exitoso, "referencia": self.referencia,
                "mensaje": self.mensaje}


class PagoRechazado(Exception):
    pass


class EstrategiaPago(ABC):
    """Strategy: contrato unico para cobrar un monto."""

    nombre = None
    prefijo = "PAGO"

    @abstractmethod
    def cobrar(self, monto, datos):
        """Devuelve un ResultadoPago. No lanza excepciones por rechazo."""

    def _referencia(self):
        return "%s-%06d" % (self.prefijo, random.randint(0, 999999))


class PagoTarjeta(EstrategiaPago):

    nombre = "tarjeta"
    prefijo = "TARJ"

    def cobrar(self, monto, datos):
        numero = str(datos.get("numero", ""))
        if len(numero) != 16 or not numero.isdigit():
            return ResultadoPago(False, mensaje="Numero de tarjeta invalido")
        if not datos.get("cvv"):
            return ResultadoPago(False, mensaje="Falta el CVV")
        return ResultadoPago(True, self._referencia(),
                             "Aprobado con tarjeta terminada en %s" % numero[-4:])


class PagoPayPal(EstrategiaPago):

    nombre = "paypal"
    prefijo = "PP"

    def cobrar(self, monto, datos):
        correo = str(datos.get("correo", ""))
        if "@" not in correo:
            return ResultadoPago(False, mensaje="Correo de PayPal invalido")
        return ResultadoPago(True, self._referencia(),
                             "Aprobado con PayPal (%s)" % correo)


class PagoSaldo(EstrategiaPago):
    """Billetera interna: la unica estrategia que puede rechazar por fondos."""

    nombre = "saldo"
    prefijo = "SALDO"

    def __init__(self, base_datos=None, usuario_id=USUARIO_ID):
        self.base_datos = base_datos or BaseDatos.instancia()
        self.usuario_id = usuario_id

    def cobrar(self, monto, datos):
        fila = self.base_datos.consultar_uno(
            "SELECT saldo FROM billetera WHERE usuario_id = ?", (self.usuario_id,))
        saldo = fila["saldo"] if fila else 0.0
        if saldo < monto:
            return ResultadoPago(
                False, mensaje="Saldo insuficiente: tienes %.2f y necesitas %.2f"
                % (saldo, monto))
        self.base_datos.ejecutar(
            "UPDATE billetera SET saldo = saldo - ? WHERE usuario_id = ?",
            (monto, self.usuario_id))
        return ResultadoPago(True, self._referencia(),
                             "Pagado con saldo de la billetera")


class PagoCripto(EstrategiaPago):

    nombre = "cripto"
    prefijo = "CRIP"

    def cobrar(self, monto, datos):
        wallet = str(datos.get("wallet", ""))
        if not wallet.startswith("0x"):
            return ResultadoPago(False, mensaje="Direccion de wallet invalida")
        return ResultadoPago(True, self._referencia(),
                             "Transaccion enviada a la cadena")


_ESTRATEGIAS = {}


def registrar_estrategia(clase):
    """Un medio de pago nuevo se registra sin tocar el codigo existente."""
    _ESTRATEGIAS[clase.nombre] = clase
    return clase


def obtener_estrategia(nombre):
    try:
        return _ESTRATEGIAS[nombre]()
    except KeyError:
        raise PagoRechazado(
            "Medio de pago no soportado: %r. Disponibles: %s"
            % (nombre, ", ".join(sorted(_ESTRATEGIAS)))
        )


def medios_disponibles():
    return sorted(_ESTRATEGIAS)


for _clase in (PagoTarjeta, PagoPayPal, PagoSaldo, PagoCripto):
    registrar_estrategia(_clase)
