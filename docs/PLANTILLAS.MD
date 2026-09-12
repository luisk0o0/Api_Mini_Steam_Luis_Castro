Crear un juego
json
{
  "tipo": "juego",
  "nombre": "Neon Drift",
  "precio_base": 75000,
  "etiquetas": ["carreras", "arcade"],
  "peso_gb": 20
}

Borra juego_base_id: un juego no tiene juego base.

Crear un DLC
json
{
  "tipo": "dlc",
  "nombre": "Neon Drift: Circuitos",
  "precio_base": 20000,
  "etiquetas": ["carreras"],
  "juego_base_id": 1
}

Borra peso_gb, y juego_base_id tiene que ser el id de un producto que ya existe (1 a 5 con el catálogo sembrado). Si pones uno inexistente te responde 400 con "El juego base #X no existe".

------------------- PLANTILLA PAGOS----------------------

Tarjeta

json
{"metodo_pago": "tarjeta", "datos": {"numero": "4111111111111111", "cvv": "123"}}

PayPal:

json
{"metodo_pago": "paypal", "datos": {"correo": "yo@correo.com"}}

Saldo:

json
{"metodo_pago": "saldo", "datos": {}}

Cripto:

json
{"metodo_pago": "cripto", "datos": {"wallet": "0xabc123"}}