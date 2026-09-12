"""Version ANTES: toda la tienda vive en una sola clase.

`TiendaSteam` es un objeto, si. Pero es un objeto que hace absolutamente todo:
abre conexiones, crea productos, calcula descuentos, cobra, envia correos,
actualiza estadisticas y escribe logs. Es el clasico "God Object".
"""

import datetime
import os
import random
import sqlite3

from antes.modelos import USUARIO_ID, Producto

RUTA_DB = os.environ.get("STEAM_DB", os.path.join(os.path.dirname(__file__), "steam.db"))

IVA = 0.19


class TiendaSteam:

    def __init__(self):
        self.iva = IVA
        self.log = []

    # ------------------------------------------------------------------
    # Acceso a datos
    # ------------------------------------------------------------------
    def _conexion(self):
        """Abre una conexion NUEVA cada vez que alguien la necesita."""
        conexion = sqlite3.connect(RUTA_DB)
        conexion.row_factory = sqlite3.Row
        return conexion

    def crear_esquema(self):
        con = self._conexion()
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
        con.commit()
        con.close()
        self.sembrar_datos()

    def sembrar_datos(self):
        con = self._conexion()
        fila = con.execute("SELECT COUNT(*) AS n FROM productos").fetchone()
        if fila["n"] == 0:
            con.executemany(
                "INSERT INTO productos (tipo, nombre, precio_base, etiquetas, juego_base_id, peso_gb)"
                " VALUES (?,?,?,?,?,?)",
                [
                    ("juego", "Hollow Depths", 120000, "metroidvania,indie", None, 12.5),
                    ("juego", "Silent Manor", 90000, "terror,aventura", None, 30.0),
                    ("juego", "Galactic Freight", 160000, "simulacion,espacio", None, 45.0),
                    ("dlc", "Hollow Depths: Abismo", 40000, "metroidvania,indie", 1, None),
                    ("dlc", "Silent Manor: Noche Eterna", 35000, "terror", 2, None),
                ],
            )
        con.execute("INSERT OR IGNORE INTO billetera (usuario_id, saldo) VALUES (?, ?)",
                    (USUARIO_ID, 200000.0))
        con.commit()
        con.close()

    def _fila_a_producto(self, fila):
        return Producto(
            id=fila["id"],
            tipo=fila["tipo"],
            nombre=fila["nombre"],
            precio_base=fila["precio_base"],
            etiquetas=[e for e in fila["etiquetas"].split(",") if e],
            juego_base_id=fila["juego_base_id"],
            peso_gb=fila["peso_gb"],
        )

    # ------------------------------------------------------------------
    # Alta de productos
    # ------------------------------------------------------------------
    def crear_producto(self, datos):
        """Crea un producto decidiendo el tipo con if/elif."""
        tipo = datos.get("tipo")
        if tipo == "juego":
            producto = Producto(
                id=None,
                tipo="juego",
                nombre=datos["nombre"],
                precio_base=datos["precio_base"],
                etiquetas=datos.get("etiquetas", []),
                juego_base_id=None,
                peso_gb=datos.get("peso_gb"),
            )
            producto.validar()
        elif tipo == "dlc":
            producto = Producto(
                id=None,
                tipo="dlc",
                nombre=datos["nombre"],
                precio_base=datos["precio_base"],
                etiquetas=datos.get("etiquetas", []),
                juego_base_id=datos.get("juego_base_id"),
                peso_gb=None,
            )
            producto.validar()
            # ademas, un DLC exige que el juego base exista
            con = self._conexion()
            fila = con.execute("SELECT id FROM productos WHERE id = ?",
                               (producto.juego_base_id,)).fetchone()
            con.close()
            if fila is None:
                raise ValueError("El juego base no existe")
        else:
            raise ValueError("Tipo de producto no soportado: %s" % tipo)

        con = self._conexion()
        cursor = con.execute(
            "INSERT INTO productos (tipo, nombre, precio_base, etiquetas, juego_base_id, peso_gb)"
            " VALUES (?,?,?,?,?,?)",
            (producto.tipo, producto.nombre, producto.precio_base,
             ",".join(producto.etiquetas), producto.juego_base_id, producto.peso_gb),
        )
        producto.id = cursor.lastrowid
        con.commit()
        con.close()
        return producto

    # ------------------------------------------------------------------
    # Precios y promociones
    # ------------------------------------------------------------------
    def calcular_precio(self, producto, fecha=None):
        """Precio final del catalogo: promocion estacional + IVA."""
        if fecha is None:
            fecha = datetime.date.today()
        mes = fecha.month
        dia = fecha.day
        precio = producto.precio_base
        promocion = None

        if (mes == 12 and dia >= 22) or (mes == 1 and dia <= 5):
            promocion = "Rebajas de Invierno"
            precio = precio * 0.70
        elif mes == 6 and dia >= 25:
            promocion = "Rebajas de Verano"
            precio = precio * 0.75
        elif mes == 7 and dia <= 9:
            promocion = "Rebajas de Verano"
            precio = precio * 0.75
        elif (mes == 10 and dia >= 27) or (mes == 11 and dia == 1):
            if "terror" in producto.etiquetas:
                promocion = "Halloween"
                precio = precio * 0.60
        elif mes == 2 and 8 <= dia <= 15:
            promocion = "Ano Nuevo Lunar"
            precio = precio * 0.80
        elif mes == 11 and 21 <= dia <= 28:
            promocion = "Rebajas de Otono"
            precio = precio * 0.80

        precio = precio * (1 + self.iva)
        return round(precio, 2), promocion

    def catalogo(self, fecha=None):
        con = self._conexion()
        filas = con.execute("SELECT * FROM productos ORDER BY id").fetchall()
        con.close()
        salida = []
        for fila in filas:
            producto = self._fila_a_producto(fila)
            precio, promocion = self.calcular_precio(producto, fecha)
            datos = producto.a_dict()
            datos["precio_final"] = precio
            datos["promocion"] = promocion
            salida.append(datos)
        return salida

    def detalle(self, producto_id, fecha=None):
        con = self._conexion()
        fila = con.execute("SELECT * FROM productos WHERE id = ?", (producto_id,)).fetchone()
        con.close()
        if fila is None:
            return None
        producto = self._fila_a_producto(fila)
        precio, promocion = self.calcular_precio(producto, fecha)
        datos = producto.a_dict()
        datos["precio_final"] = precio
        datos["promocion"] = promocion
        return datos

    # ------------------------------------------------------------------
    # Carrito
    # ------------------------------------------------------------------
    def agregar_al_carrito(self, producto_id):
        con = self._conexion()
        fila = con.execute("SELECT id FROM productos WHERE id = ?", (producto_id,)).fetchone()
        if fila is None:
            con.close()
            raise ValueError("El producto no existe")
        ya = con.execute("SELECT 1 FROM biblioteca WHERE usuario_id = ? AND producto_id = ?",
                         (USUARIO_ID, producto_id)).fetchone()
        if ya is not None:
            con.close()
            raise ValueError("Ya tienes ese producto en tu biblioteca")
        con.execute("INSERT OR IGNORE INTO carrito (usuario_id, producto_id) VALUES (?,?)",
                    (USUARIO_ID, producto_id))
        con.commit()
        con.close()
        return True

    def quitar_del_carrito(self, producto_id):
        con = self._conexion()
        cursor = con.execute("DELETE FROM carrito WHERE usuario_id = ? AND producto_id = ?",
                             (USUARIO_ID, producto_id))
        con.commit()
        borrados = cursor.rowcount
        con.close()
        if borrados == 0:
            raise ValueError("Ese producto no esta en el carrito")
        return True

    def ver_carrito(self, fecha=None):
        """Ojo: aqui se vuelve a calcular el descuento, con otra copia del if/elif."""
        if fecha is None:
            fecha = datetime.date.today()
        mes = fecha.month
        dia = fecha.day
        con = self._conexion()
        filas = con.execute(
            "SELECT p.* FROM carrito c JOIN productos p ON p.id = c.producto_id"
            " WHERE c.usuario_id = ? ORDER BY p.id", (USUARIO_ID,)).fetchall()
        con.close()

        items = []
        subtotal = 0.0
        for fila in filas:
            producto = self._fila_a_producto(fila)
            precio = producto.precio_base
            promocion = None
            if (mes == 12 and dia >= 22) or (mes == 1 and dia <= 5):
                promocion = "Rebajas de Invierno"
                precio = precio * 0.70
            elif mes == 6 and dia >= 25:
                promocion = "Rebajas de Verano"
                precio = precio * 0.75
            elif mes == 7 and dia <= 9:
                promocion = "Rebajas de Verano"
                precio = precio * 0.75
            elif (mes == 10 and dia >= 27) or (mes == 11 and dia == 1):
                if "terror" in producto.etiquetas:
                    promocion = "Halloween"
                    precio = precio * 0.60
            elif mes == 2 and 8 <= dia <= 15:
                promocion = "Ano Nuevo Lunar"
                precio = precio * 0.80
            elif mes == 11 and 21 <= dia <= 28:
                promocion = "Rebajas de Otono"
                precio = precio * 0.80
            # NOTA: aqui falta el IVA que si se aplica en calcular_precio()
            precio = round(precio, 2)
            subtotal += precio
            datos = producto.a_dict()
            datos["precio_final"] = precio
            datos["promocion"] = promocion
            items.append(datos)
        return {"items": items, "subtotal": round(subtotal, 2)}

    # ------------------------------------------------------------------
    # Pagos
    # ------------------------------------------------------------------
    def procesar_pago(self, metodo, monto, datos):
        """Cobra el monto decidiendo el medio de pago con if/elif."""
        datos = datos or {}
        if metodo == "tarjeta":
            numero = datos.get("numero", "")
            if len(numero) != 16 or not numero.isdigit():
                return False, None, "Numero de tarjeta invalido"
            if not datos.get("cvv"):
                return False, None, "Falta el CVV"
            referencia = "TARJ-%06d" % random.randint(0, 999999)
            return True, referencia, "Aprobado con tarjeta terminada en %s" % numero[-4:]
        elif metodo == "paypal":
            correo = datos.get("correo", "")
            if "@" not in correo:
                return False, None, "Correo de PayPal invalido"
            referencia = "PP-%06d" % random.randint(0, 999999)
            return True, referencia, "Aprobado con PayPal (%s)" % correo
        elif metodo == "saldo":
            con = self._conexion()
            fila = con.execute("SELECT saldo FROM billetera WHERE usuario_id = ?",
                               (USUARIO_ID,)).fetchone()
            saldo = fila["saldo"] if fila else 0.0
            if saldo < monto:
                con.close()
                return False, None, "Saldo insuficiente en la billetera"
            con.execute("UPDATE billetera SET saldo = saldo - ? WHERE usuario_id = ?",
                        (monto, USUARIO_ID))
            con.commit()
            con.close()
            referencia = "SALDO-%06d" % random.randint(0, 999999)
            return True, referencia, "Pagado con saldo de la billetera"
        elif metodo == "cripto":
            wallet = datos.get("wallet", "")
            if not wallet.startswith("0x"):
                return False, None, "Wallet invalida"
            referencia = "CRIP-%06d" % random.randint(0, 999999)
            return True, referencia, "Transaccion enviada a la cadena"
        else:
            return False, None, "Medio de pago no soportado: %s" % metodo

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------
    def checkout(self, metodo, datos_pago=None, fecha=None):
        """Un solo metodo que valida, cobra, guarda, notifica y audita."""
        if fecha is None:
            fecha = datetime.date.today()
        mes = fecha.month
        dia = fecha.day

        con = self._conexion()
        filas = con.execute(
            "SELECT p.* FROM carrito c JOIN productos p ON p.id = c.producto_id"
            " WHERE c.usuario_id = ? ORDER BY p.id", (USUARIO_ID,)).fetchall()
        con.close()
        if len(filas) == 0:
            raise ValueError("El carrito esta vacio")

        # 1) recalcular precios (tercera copia del mismo if/elif)
        total = 0.0
        comprados = []
        for fila in filas:
            producto = self._fila_a_producto(fila)
            precio = producto.precio_base
            if (mes == 12 and dia >= 22) or (mes == 1 and dia <= 5):
                precio = precio * 0.70
            elif mes == 6 and dia >= 25:
                precio = precio * 0.75
            elif mes == 7 and dia <= 9:
                precio = precio * 0.75
            elif (mes == 10 and dia >= 27) or (mes == 11 and dia == 1):
                if "terror" in producto.etiquetas:
                    precio = precio * 0.60
            elif mes == 2 and 8 <= dia <= 15:
                precio = precio * 0.80
            elif mes == 11 and 21 <= dia <= 28:
                precio = precio * 0.80
            precio = round(precio * (1 + self.iva), 2)
            total += precio
            comprados.append((producto, precio))
        total = round(total, 2)

        # 2) cobrar
        aprobado, referencia, mensaje = self.procesar_pago(metodo, total, datos_pago)
        if not aprobado:
            raise ValueError(mensaje)

        # 3) registrar la compra
        con = self._conexion()
        con.execute(
            "INSERT INTO compras (usuario_id, total, metodo_pago, referencia, fecha)"
            " VALUES (?,?,?,?,?)",
            (USUARIO_ID, total, metodo, referencia, fecha.isoformat()))

        # 4) mover el carrito a la biblioteca
        for producto, precio in comprados:
            con.execute(
                "INSERT OR IGNORE INTO biblioteca (usuario_id, producto_id, fecha, precio_pagado)"
                " VALUES (?,?,?,?)",
                (USUARIO_ID, producto.id, fecha.isoformat(), precio))

        # 5) actualizar estadisticas de ventas
        for producto, _precio in comprados:
            con.execute("INSERT INTO estadisticas (producto_id, ventas) VALUES (?, 1)"
                        " ON CONFLICT(producto_id) DO UPDATE SET ventas = ventas + 1",
                        (producto.id,))

        # 6) vaciar el carrito
        con.execute("DELETE FROM carrito WHERE usuario_id = ?", (USUARIO_ID,))
        con.commit()
        con.close()

        # 7) "enviar" el correo de confirmacion
        cuerpo = "Gracias por tu compra. Referencia %s por $%s" % (referencia, total)
        print("[CORREO] para usuario %s: %s" % (USUARIO_ID, cuerpo))

        # 8) auditar
        self.log.append("compra %s total %s metodo %s" % (referencia, total, metodo))

        return {
            "referencia": referencia,
            "total": total,
            "metodo_pago": metodo,
            "mensaje": mensaje,
            "productos": [p.nombre for p, _ in comprados],
        }

    # ------------------------------------------------------------------
    # Biblioteca
    # ------------------------------------------------------------------
    def biblioteca(self):
        con = self._conexion()
        filas = con.execute(
            "SELECT p.*, b.fecha AS fecha_compra, b.precio_pagado FROM biblioteca b"
            " JOIN productos p ON p.id = b.producto_id"
            " WHERE b.usuario_id = ? ORDER BY b.fecha, p.id", (USUARIO_ID,)).fetchall()
        con.close()
        salida = []
        for fila in filas:
            producto = self._fila_a_producto(fila)
            datos = producto.a_dict()
            datos["fecha_compra"] = fila["fecha_compra"]
            datos["precio_pagado"] = fila["precio_pagado"]
            salida.append(datos)
        return salida
