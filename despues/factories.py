"""PATRON 2 - FACTORY METHOD (creacional).

Problema que resuelve: en `antes/tienda.py`, `crear_producto()` decidia con un
if/elif que objeto construir y ademas repetia dentro de cada rama la validacion
y el armado de campos. Cada tipo nuevo obligaba a editar ese metodo (viola OCP).

Aqui cada tipo de producto tiene su propia fabrica concreta. La operacion
`registrar()` es igual para todos y delega la construccion en el metodo
fabrica `crear_producto()`, que cada subclase implementa a su manera.

Roles GoF:
    Creator          -> FabricaProducto (declara el metodo fabrica)
    ConcreteCreator  -> FabricaJuego, FabricaDLC
    Product          -> Producto
    ConcreteProduct  -> Juego, DLC

El diccionario `_REGISTRO` NO es el patron: es solo el mecanismo por el que el
cliente elige la fabrica. Se usa un diccionario justamente para no reintroducir
el if/elif que estamos eliminando.
"""

from abc import ABC, abstractmethod

from despues.db import BaseDatos
from despues.modelos import DLC, Juego, Producto


class TipoProductoNoSoportado(Exception):
    pass


class FabricaProducto(ABC):
    """Creator."""

    tipo = None

    def registrar(self, datos):
        """Operacion comun: crea el producto y valida su contexto."""
        producto = self.crear_producto(datos)
        self.validar_contexto(producto)
        return producto

    @abstractmethod
    def crear_producto(self, datos):
        """Metodo fabrica: cada subclase decide que instanciar y como."""

    @abstractmethod
    def desde_fila(self, fila):
        """Reconstruye el producto a partir de una fila de la base de datos."""

    def validar_contexto(self, producto):
        """Gancho opcional: reglas que dependen del resto del catalogo."""
        return None


class FabricaJuego(FabricaProducto):

    tipo = "juego"

    def crear_producto(self, datos):
        return Juego(
            nombre=datos["nombre"],
            precio_base=datos["precio_base"],
            peso_gb=datos.get("peso_gb"),
            etiquetas=datos.get("etiquetas"),
        )

    def desde_fila(self, fila):
        return Juego(
            nombre=fila["nombre"],
            precio_base=fila["precio_base"],
            peso_gb=fila["peso_gb"],
            etiquetas=[e for e in fila["etiquetas"].split(",") if e],
            id=fila["id"],
        )


class FabricaDLC(FabricaProducto):

    tipo = "dlc"

    def __init__(self, existe_producto=None):
        # Se inyecta la comprobacion para no atar la fabrica a SQLite (DIP).
        self._existe_producto = existe_producto or self._existe_en_bd

    @staticmethod
    def _existe_en_bd(producto_id):
        fila = BaseDatos.instancia().consultar_uno(
            "SELECT 1 FROM productos WHERE id = ?", (producto_id,))
        return fila is not None

    def crear_producto(self, datos):
        return DLC(
            nombre=datos["nombre"],
            precio_base=datos["precio_base"],
            juego_base_id=datos.get("juego_base_id"),
            etiquetas=datos.get("etiquetas"),
        )

    def validar_contexto(self, producto):
        if not self._existe_producto(producto.juego_base_id):
            raise ValueError("El juego base #%s no existe" % producto.juego_base_id)

    def desde_fila(self, fila):
        return DLC(
            nombre=fila["nombre"],
            precio_base=fila["precio_base"],
            juego_base_id=fila["juego_base_id"],
            etiquetas=[e for e in fila["etiquetas"].split(",") if e],
            id=fila["id"],
        )


_REGISTRO = {}


def registrar_fabrica(fabrica):
    """Da de alta una fabrica. Un tipo nuevo se agrega sin tocar este archivo."""
    _REGISTRO[fabrica.tipo] = fabrica
    return fabrica


def obtener_fabrica(tipo):
    try:
        return _REGISTRO[tipo]
    except KeyError:
        raise TipoProductoNoSoportado(
            "Tipo de producto no soportado: %r. Disponibles: %s"
            % (tipo, ", ".join(sorted(_REGISTRO)))
        )


def tipos_disponibles():
    return sorted(_REGISTRO)


registrar_fabrica(FabricaJuego())
registrar_fabrica(FabricaDLC())
