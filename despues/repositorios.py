"""Repositorios: aislan el SQL del resto del sistema.

No son un patron GoF (son un patron de arquitectura, Repository de Fowler), asi
que no cuentan dentro de los cinco exigidos. Estan aqui porque sin ellos los
servicios volverian a mezclar reglas de negocio con sentencias SQL, que era uno
de los problemas de la version ANTES.

Notese que la reconstruccion de objetos desde la base de datos tampoco usa
if/elif: delega en las mismas fabricas del Factory Method.
"""

from despues.db import BaseDatos
from despues.factories import obtener_fabrica
from despues.modelos import USUARIO_ID


def fila_a_producto(fila):
    """Reconstruye el objeto correcto delegando en su fabrica (sin if/elif)."""
    return obtener_fabrica(fila["tipo"]).desde_fila(fila)


class RepositorioProductos:

    def __init__(self, base_datos=None):
        self.base_datos = base_datos or BaseDatos.instancia()

    def todos(self):
        filas = self.base_datos.consultar_todos("SELECT * FROM productos ORDER BY id")
        return [fila_a_producto(fila) for fila in filas]

    def por_id(self, producto_id):
        fila = self.base_datos.consultar_uno(
            "SELECT * FROM productos WHERE id = ?", (producto_id,))
        return fila_a_producto(fila) if fila else None

    def existe(self, producto_id):
        return self.base_datos.consultar_uno(
            "SELECT 1 FROM productos WHERE id = ?", (producto_id,)) is not None

    def guardar(self, producto):
        cursor = self.base_datos.ejecutar(
            "INSERT INTO productos (tipo, nombre, precio_base, etiquetas,"
            " juego_base_id, peso_gb) VALUES (?,?,?,?,?,?)",
            (producto.tipo, producto.nombre, producto.precio_base,
             ",".join(producto.etiquetas), producto.juego_base_id, producto.peso_gb))
        producto.id = cursor.lastrowid
        return producto


class RepositorioCarrito:

    def __init__(self, base_datos=None, usuario_id=USUARIO_ID):
        self.base_datos = base_datos or BaseDatos.instancia()
        self.usuario_id = usuario_id

    def items(self):
        filas = self.base_datos.consultar_todos(
            "SELECT p.* FROM carrito c JOIN productos p ON p.id = c.producto_id"
            " WHERE c.usuario_id = ? ORDER BY p.id", (self.usuario_id,))
        return [fila_a_producto(fila) for fila in filas]

    def contiene(self, producto_id):
        return self.base_datos.consultar_uno(
            "SELECT 1 FROM carrito WHERE usuario_id = ? AND producto_id = ?",
            (self.usuario_id, producto_id)) is not None

    def agregar(self, producto_id):
        self.base_datos.ejecutar(
            "INSERT OR IGNORE INTO carrito (usuario_id, producto_id) VALUES (?,?)",
            (self.usuario_id, producto_id))

    def quitar(self, producto_id):
        cursor = self.base_datos.ejecutar(
            "DELETE FROM carrito WHERE usuario_id = ? AND producto_id = ?",
            (self.usuario_id, producto_id))
        return cursor.rowcount > 0

    def vaciar(self):
        self.base_datos.ejecutar(
            "DELETE FROM carrito WHERE usuario_id = ?", (self.usuario_id,))


class RepositorioBiblioteca:

    def __init__(self, base_datos=None, usuario_id=USUARIO_ID):
        self.base_datos = base_datos or BaseDatos.instancia()
        self.usuario_id = usuario_id

    def posee(self, producto_id):
        if producto_id is None:
            return False
        return self.base_datos.consultar_uno(
            "SELECT 1 FROM biblioteca WHERE usuario_id = ? AND producto_id = ?",
            (self.usuario_id, producto_id)) is not None

    def listar(self):
        filas = self.base_datos.consultar_todos(
            "SELECT p.*, b.fecha AS fecha_compra, b.precio_pagado"
            " FROM biblioteca b JOIN productos p ON p.id = b.producto_id"
            " WHERE b.usuario_id = ? ORDER BY b.fecha, p.id", (self.usuario_id,))
        salida = []
        for fila in filas:
            datos = fila_a_producto(fila).a_dict()
            datos["fecha_compra"] = fila["fecha_compra"]
            datos["precio_pagado"] = fila["precio_pagado"]
            salida.append(datos)
        return salida


class RepositorioCompras:

    def __init__(self, base_datos=None, usuario_id=USUARIO_ID):
        self.base_datos = base_datos or BaseDatos.instancia()
        self.usuario_id = usuario_id

    def registrar(self, total, metodo_pago, referencia, fecha):
        cursor = self.base_datos.ejecutar(
            "INSERT INTO compras (usuario_id, total, metodo_pago, referencia, fecha)"
            " VALUES (?,?,?,?,?)",
            (self.usuario_id, total, metodo_pago, referencia, fecha.isoformat()))
        return cursor.lastrowid
