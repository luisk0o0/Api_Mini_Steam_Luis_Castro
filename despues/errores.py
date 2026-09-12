"""Errores de dominio.

Se separan de HTTP a proposito: el dominio no sabe que existe FastAPI. La capa
web (main.py) es la unica que traduce estos errores a codigos de estado.
"""


class ErrorDominio(Exception):
    """Base de todos los errores de negocio."""


class ProductoNoEncontrado(ErrorDominio):
    pass


class ReglaDeNegocio(ErrorDominio):
    """El usuario pidio algo que las reglas no permiten."""


class CarritoVacio(ReglaDeNegocio):
    pass
