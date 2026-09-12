"""PATRON 1 - SINGLETON (creacional).

Problema que resuelve: en la version ANTES cada operacion abria una conexion
SQLite nueva (`antes/tienda.py`, metodo `_conexion`) y casi ninguna se cerraba.
Ademas el esquema se creaba desde cualquier parte, sin un punto de control.

Aqui `BaseDatos` garantiza una unica instancia con una unica conexion viva
sobre el archivo `steam.db`, y ofrece un punto de acceso global controlado.

Roles GoF:
    Singleton -> BaseDatos (constructor controlado + acceso via instancia()).
"""

import os
import sqlite3
import threading
from contextlib import contextmanager

RUTA_POR_DEFECTO = os.environ.get(
    "STEAM_DB", os.path.join(os.path.dirname(__file__), "steam.db")
)


class BaseDatos:
    """Unica puerta de entrada a SQLite."""

    _instancia = None
    _cerrojo_clase = threading.Lock()

    def __new__(cls, ruta=None):
        # Doble verificacion: barata cuando ya existe, segura cuando no.
        if cls._instancia is None:
            with cls._cerrojo_clase:
                if cls._instancia is None:
                    instancia = super().__new__(cls)
                    instancia._listo = False
                    cls._instancia = instancia
        return cls._instancia

    def __init__(self, ruta=None):
        if self._listo:
            # Ya inicializado: las llamadas siguientes no reconstruyen nada.
            return
        self.ruta = ruta or RUTA_POR_DEFECTO
        self._conexion = sqlite3.connect(self.ruta, check_same_thread=False)
        self._conexion.row_factory = sqlite3.Row
        self._conexion.execute("PRAGMA foreign_keys = ON")
        self._cerrojo = threading.RLock()
        self._listo = True

    # -- punto de acceso -------------------------------------------------
    @classmethod
    def instancia(cls, ruta=None):
        """Punto de acceso global explicito (mas legible que `BaseDatos()`)."""
        return cls(ruta)

    @classmethod
    def reiniciar(cls, ruta=None):
        """Solo para pruebas: destruye la instancia y crea otra.

        Un Singleton sin esta puerta trasera vuelve el codigo casi imposible
        de testear; la exponemos de forma explicita y documentada.
        """
        if cls._instancia is not None and getattr(cls._instancia, "_listo", False):
            cls._instancia._conexion.close()
        cls._instancia = None
        return cls(ruta)

    # -- operaciones -----------------------------------------------------
    @property
    def conexion(self):
        return self._conexion

    def ejecutar(self, sql, parametros=()):
        with self._cerrojo:
            cursor = self._conexion.execute(sql, parametros)
            self._conexion.commit()
            return cursor

    def consultar_todos(self, sql, parametros=()):
        with self._cerrojo:
            return self._conexion.execute(sql, parametros).fetchall()

    def consultar_uno(self, sql, parametros=()):
        with self._cerrojo:
            return self._conexion.execute(sql, parametros).fetchone()

    @contextmanager
    def transaccion(self):
        """Agrupa varias escrituras en una sola unidad atomica."""
        with self._cerrojo:
            try:
                yield self._conexion
                self._conexion.commit()
            except Exception:
                self._conexion.rollback()
                raise

    # -- esquema ---------------------------------------------------------
    def crear_esquema(self):
        with self.transaccion() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                nombre TEXT NOT NULL,
                precio_base REAL NOT NULL,
                etiquetas TEXT NOT NULL DEFAULT '',
                juego_base_id INTEGER,
                peso_gb REAL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS carrito (
                usuario_id INTEGER NOT NULL,
                producto_id INTEGER NOT NULL,
                PRIMARY KEY (usuario_id, producto_id))""")
            con.execute("""CREATE TABLE IF NOT EXISTS biblioteca (
                usuario_id INTEGER NOT NULL,
                producto_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                precio_pagado REAL NOT NULL,
                PRIMARY KEY (usuario_id, producto_id))""")
            con.execute("""CREATE TABLE IF NOT EXISTS compras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                total REAL NOT NULL,
                metodo_pago TEXT NOT NULL,
                referencia TEXT NOT NULL,
                fecha TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS billetera (
                usuario_id INTEGER PRIMARY KEY,
                saldo REAL NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS estadisticas (
                producto_id INTEGER PRIMARY KEY,
                ventas INTEGER NOT NULL DEFAULT 0)""")
            con.execute("""CREATE TABLE IF NOT EXISTS notificaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                asunto TEXT NOT NULL,
                cuerpo TEXT NOT NULL,
                fecha TEXT NOT NULL)""")

    def sembrar_datos(self, usuario_id=1, saldo_inicial=200000.0):
        fila = self.consultar_uno("SELECT COUNT(*) AS n FROM productos")
        with self.transaccion() as con:
            if fila["n"] == 0:
                con.executemany(
                    "INSERT INTO productos (tipo, nombre, precio_base, etiquetas,"
                    " juego_base_id, peso_gb) VALUES (?,?,?,?,?,?)",
                    [
                        ("juego", "Hollow Depths", 120000, "metroidvania,indie", None, 12.5),
                        ("juego", "Silent Manor", 90000, "terror,aventura", None, 30.0),
                        ("juego", "Galactic Freight", 160000, "simulacion,espacio", None, 45.0),
                        ("dlc", "Hollow Depths: Abismo", 40000, "metroidvania,indie", 1, None),
                        ("dlc", "Silent Manor: Noche Eterna", 35000, "terror", 2, None),
                    ],
                )
            con.execute("INSERT OR IGNORE INTO billetera (usuario_id, saldo) VALUES (?,?)",
                        (usuario_id, saldo_inicial))
