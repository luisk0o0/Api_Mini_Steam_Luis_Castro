"""Modelo de dominio de la version DESPUES.

En vez de una clase `Producto` con un campo `tipo` de texto y un if/elif en
cada metodo, hay una jerarquia real: cada subtipo sabe comportarse solo.
Agregar un tipo nuevo ya no obliga a tocar los metodos existentes (OCP).
"""

from abc import ABC, abstractmethod

USUARIO_ID = 1  # limitacion conocida: no hay autenticacion


class Producto(ABC):
    """Producto vendible del catalogo."""

    def __init__(self, nombre, precio_base, etiquetas=None, id=None):
        if precio_base < 0:
            raise ValueError("El precio no puede ser negativo")
        self.id = id
        self.nombre = nombre
        self.precio_base = float(precio_base)
        self.etiquetas = list(etiquetas or [])

    @property
    @abstractmethod
    def tipo(self):
        """Discriminador que se persiste en la base de datos."""

    @abstractmethod
    def descripcion(self):
        """Texto corto que se muestra en el catalogo."""

    @property
    def juego_base_id(self):
        return None

    @property
    def peso_gb(self):
        return None

    def tiene_etiqueta(self, etiqueta):
        return etiqueta in self.etiquetas

    def a_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "nombre": self.nombre,
            "precio_base": self.precio_base,
            "etiquetas": self.etiquetas,
            "descripcion": self.descripcion(),
        }


class Juego(Producto):

    def __init__(self, nombre, precio_base, peso_gb, etiquetas=None, id=None):
        super().__init__(nombre, precio_base, etiquetas, id)
        if peso_gb is None or peso_gb <= 0:
            raise ValueError("Un juego necesita peso_gb mayor que cero")
        self._peso_gb = float(peso_gb)

    @property
    def tipo(self):
        return "juego"

    @property
    def peso_gb(self):
        return self._peso_gb

    def descripcion(self):
        return "Juego base - %s GB" % self._peso_gb

    def a_dict(self):
        datos = super().a_dict()
        datos["peso_gb"] = self._peso_gb
        return datos


class DLC(Producto):

    def __init__(self, nombre, precio_base, juego_base_id, etiquetas=None, id=None):
        super().__init__(nombre, precio_base, etiquetas, id)
        if juego_base_id is None:
            raise ValueError("Un DLC necesita juego_base_id")
        self._juego_base_id = int(juego_base_id)

    @property
    def tipo(self):
        return "dlc"

    @property
    def juego_base_id(self):
        return self._juego_base_id

    def descripcion(self):
        return "Contenido adicional del juego #%s" % self._juego_base_id

    def a_dict(self):
        datos = super().a_dict()
        datos["juego_base_id"] = self._juego_base_id
        return datos
