"""Modelo de dominio de la version ANTES.

Si hay objetos: existe una clase `Producto`. Lo que NO hay es diseno.
`Producto` es una unica clase que intenta representar a la vez un juego y un
DLC, distinguiendolos con un campo de texto `tipo`. Cada vez que el
comportamiento depende del tipo, aparece un if/elif dentro del metodo.
"""

USUARIO_ID = 1  # no hay autenticacion: siempre es el mismo usuario


class Producto:
    """Un unico tipo para juegos y DLCs (y para lo que venga despues)."""

    def __init__(self, id, tipo, nombre, precio_base, etiquetas,
                 juego_base_id=None, peso_gb=None):
        self.id = id
        self.tipo = tipo                    # "juego" | "dlc" -> string magico
        self.nombre = nombre
        self.precio_base = precio_base
        self.etiquetas = etiquetas          # lista de strings
        self.juego_base_id = juego_base_id  # solo tiene sentido si tipo == "dlc"
        self.peso_gb = peso_gb              # solo tiene sentido si tipo == "juego"

    def validar(self):
        """Valida el producto segun su tipo."""
        if self.precio_base < 0:
            raise ValueError("El precio no puede ser negativo")
        if self.tipo == "juego":
            if self.peso_gb is None or self.peso_gb <= 0:
                raise ValueError("Un juego necesita peso_gb mayor que cero")
        elif self.tipo == "dlc":
            if self.juego_base_id is None:
                raise ValueError("Un DLC necesita juego_base_id")
        else:
            raise ValueError("Tipo de producto no soportado: %s" % self.tipo)

    def etiqueta_visual(self):
        """Texto que se muestra en el catalogo."""
        if self.tipo == "juego":
            return "Juego base - %s GB" % self.peso_gb
        elif self.tipo == "dlc":
            return "Contenido adicional del juego #%s" % self.juego_base_id
        else:
            return "Producto"

    def requiere_juego_base(self):
        if self.tipo == "juego":
            return False
        elif self.tipo == "dlc":
            return True
        else:
            return False

    def a_dict(self):
        datos = {
            "id": self.id,
            "tipo": self.tipo,
            "nombre": self.nombre,
            "precio_base": self.precio_base,
            "etiquetas": self.etiquetas,
            "descripcion": self.etiqueta_visual(),
        }
        # Campos que solo aplican a un tipo, pero viven en todos los objetos.
        if self.tipo == "juego":
            datos["peso_gb"] = self.peso_gb
        elif self.tipo == "dlc":
            datos["juego_base_id"] = self.juego_base_id
        return datos
