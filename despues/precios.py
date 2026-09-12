"""PATRON 3 - DECORATOR (estructural).

Problema que resuelve: en la version ANTES el calculo del precio era una cadena
de if/elif copiada en TRES lugares (`calcular_precio`, `ver_carrito` y
`checkout` de `antes/tienda.py`). Las copias ya habian divergido: la del
carrito se olvidaba del IVA, asi que el subtotal mostrado no coincidia con lo
que se cobraba.

Aqui el precio se compone envolviendo objetos: cada regla (promocion, descuento
de fidelidad, impuesto) es un decorador independiente que se puede agregar,
quitar o reordenar sin tocar a los demas. Una sola cadena alimenta a /games,
/cart y /checkout, asi que ya no pueden divergir.

Roles GoF:
    Component         -> ComponentePrecio
    ConcreteComponent -> PrecioBase
    Decorator         -> DecoradorPrecio
    ConcreteDecorator -> DescuentoEstacional, DescuentoFidelidadDLC, ImpuestoIVA
"""

import datetime
from abc import ABC, abstractmethod

TASA_IVA = 0.19


# ----------------------------------------------------------------------
# Promociones estacionales (excluyentes entre si)
# ----------------------------------------------------------------------
class Promocion:
    """Objeto-valor: una temporada de rebajas al estilo Steam."""

    def __init__(self, nombre, porcentaje, desde, hasta, etiqueta_requerida=None):
        self.nombre = nombre
        self.porcentaje = porcentaje          # 0.30 => 30% de descuento
        self.desde = desde                    # (mes, dia)
        self.hasta = hasta                    # (mes, dia)
        self.etiqueta_requerida = etiqueta_requerida

    def vigente_en(self, fecha):
        inicio, fin = self.desde, self.hasta
        actual = (fecha.month, fecha.day)
        if inicio <= fin:
            return inicio <= actual <= fin
        # Temporada que cruza el fin de ano (ej. 22-dic a 05-ene)
        return actual >= inicio or actual <= fin

    def aplica_a(self, producto):
        if self.etiqueta_requerida is None:
            return True
        return producto.tiene_etiqueta(self.etiqueta_requerida)

    def __repr__(self):
        return "Promocion(%r, %d%%)" % (self.nombre, self.porcentaje * 100)


class CalendarioPromociones:
    """Devuelve a lo sumo UNA promocion: las temporadas son excluyentes."""

    PREDETERMINADAS = [
        Promocion("Rebajas de Invierno", 0.30, (12, 22), (1, 5)),
        Promocion("Ano Nuevo Lunar", 0.20, (2, 8), (2, 15)),
        Promocion("Rebajas de Verano", 0.25, (6, 25), (7, 9)),
        Promocion("Halloween", 0.40, (10, 27), (11, 1), etiqueta_requerida="terror"),
        Promocion("Rebajas de Otono", 0.20, (11, 21), (11, 28)),
    ]

    def __init__(self, promociones=None):
        self.promociones = list(promociones if promociones is not None
                                else self.PREDETERMINADAS)

    def vigente(self, producto, fecha=None):
        fecha = fecha or datetime.date.today()
        for promocion in self.promociones:
            if promocion.vigente_en(fecha):
                # Las temporadas no se solapan: la primera que coincida manda.
                return promocion if promocion.aplica_a(producto) else None
        return None


# ----------------------------------------------------------------------
# Cadena de decoradores
# ----------------------------------------------------------------------
class ComponentePrecio(ABC):
    """Component: cualquier cosa capaz de dar un precio."""

    @abstractmethod
    def calcular(self):
        """Devuelve el precio acumulado hasta este punto de la cadena."""

    @abstractmethod
    def desglose(self):
        """Lista de pasos aplicados, para mostrarle al usuario el porque."""


class PrecioBase(ComponentePrecio):
    """ConcreteComponent: el precio de lista, sin ninguna regla encima."""

    def __init__(self, producto):
        self.producto = producto

    def calcular(self):
        return self.producto.precio_base

    def desglose(self):
        return [{"concepto": "Precio base", "valor": round(self.producto.precio_base, 2)}]


class DecoradorPrecio(ComponentePrecio):
    """Decorator: mantiene la referencia al componente que envuelve."""

    def __init__(self, envuelto):
        self._envuelto = envuelto

    def calcular(self):
        return self._envuelto.calcular()

    def desglose(self):
        return list(self._envuelto.desglose())


class DescuentoEstacional(DecoradorPrecio):
    """Aplica la promocion de temporada vigente."""

    def __init__(self, envuelto, promocion):
        super().__init__(envuelto)
        self.promocion = promocion

    def calcular(self):
        return self._envuelto.calcular() * (1 - self.promocion.porcentaje)

    def desglose(self):
        pasos = super().desglose()
        pasos.append({
            "concepto": self.promocion.nombre,
            "valor": -round(self._envuelto.calcular() * self.promocion.porcentaje, 2),
        })
        return pasos


class DescuentoFidelidadDLC(DecoradorPrecio):
    """10% extra en un DLC si el usuario ya posee el juego base."""

    PORCENTAJE = 0.10

    def calcular(self):
        return self._envuelto.calcular() * (1 - self.PORCENTAJE)

    def desglose(self):
        pasos = super().desglose()
        pasos.append({
            "concepto": "Descuento por tener el juego base",
            "valor": -round(self._envuelto.calcular() * self.PORCENTAJE, 2),
        })
        return pasos


class ImpuestoIVA(DecoradorPrecio):
    """Se aplica al final, sobre el precio ya rebajado."""

    def __init__(self, envuelto, tasa=TASA_IVA):
        super().__init__(envuelto)
        self.tasa = tasa

    def calcular(self):
        return self._envuelto.calcular() * (1 + self.tasa)

    def desglose(self):
        pasos = super().desglose()
        pasos.append({
            "concepto": "IVA %d%%" % (self.tasa * 100),
            "valor": round(self._envuelto.calcular() * self.tasa, 2),
        })
        return pasos


# ----------------------------------------------------------------------
# Armado de la cadena
# ----------------------------------------------------------------------
class PrecioCalculado:

    def __init__(self, precio_base, precio_final, promocion, desglose):
        self.precio_base = round(precio_base, 2)
        self.precio_final = round(precio_final, 2)
        self.promocion = promocion
        self.desglose = desglose

    @property
    def ahorro(self):
        return round(self.precio_base - self.precio_final, 2)

    def a_dict(self):
        return {
            "precio_base": self.precio_base,
            "precio_final": self.precio_final,
            "promocion": self.promocion,
            "ahorro": self.ahorro,
            "desglose": self.desglose,
        }


class PoliticaPrecios:
    """Arma la cadena de decoradores segun el producto y el contexto.

    El orden importa y es una decision de diseno explicita:
        base -> promocion estacional -> fidelidad -> IVA
    El impuesto va al final porque grava el precio ya rebajado.
    """

    def __init__(self, calendario=None):
        self.calendario = calendario or CalendarioPromociones()

    def calcular(self, producto, fecha=None, posee_juego_base=False):
        componente = PrecioBase(producto)

        promocion = self.calendario.vigente(producto, fecha)
        if promocion is not None:
            componente = DescuentoEstacional(componente, promocion)

        # Se consulta la propiedad del modelo, no el string del tipo.
        if producto.juego_base_id is not None and posee_juego_base:
            componente = DescuentoFidelidadDLC(componente)

        componente = ImpuestoIVA(componente)

        return PrecioCalculado(
            precio_base=producto.precio_base,
            precio_final=componente.calcular(),
            promocion=promocion.nombre if promocion else None,
            desglose=componente.desglose(),
        )
