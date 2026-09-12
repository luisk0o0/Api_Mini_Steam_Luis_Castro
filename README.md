# Mini-Steam · Antes y Después

Trabajo de Patrones de Diseño (Especialización en Desarrollo de Software,
Universidad del Magdalena). Una API RESTful de tienda de videojuegos en dos
versiones: una deficiente y su refactorización con **5 patrones GoF**.

**Stack:** Python · FastAPI · SQLite · pytest



---

## Instalación y ejecución

```bash
pip install -r requirements.txt

# Versión antes
uvicorn antes.main:app --reload --port 8001

# Versión después
uvicorn despues.main:app --reload --port 8000

# Pruebas
pytest -q                       # 42 pruebas (dominio + API)
python -m tests.correr_pruebas  # solo dominio, sin dependencias externas
```

Documentación interactiva en `http://localhost:8000/docs`.

---

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/games` | Catálogo con precio final y promoción vigente |
| GET | `/games/{id}` | Detalle de un producto |
| POST | `/games` | Crear un producto (`juego` o `dlc`) |
| GET | `/cart` | Ver carrito con subtotal |
| POST | `/cart/{id}` | Agregar producto al carrito |
| DELETE | `/cart/{id}` | Quitar producto del carrito |
| POST | `/checkout` | Procesar la compra |
| GET | `/library` | Productos ya comprados |
| GET | `/meta` | *(extra)* tipos y medios de pago registrados |

Todos los endpoints con precio aceptan `?fecha=AAAA-MM-DD` para **simular la
fecha** y poder demostrar las rebajas estacionales en cualquier momento del año.

```bash
curl "http://localhost:8000/games?fecha=2026-12-25"       # Rebajas de Invierno
curl -X POST "http://localhost:8000/cart/1"
curl "http://localhost:8000/cart?fecha=2026-12-25"
curl -X POST "http://localhost:8000/checkout?fecha=2026-12-25" \
  -H "Content-Type: application/json" \
  -d '{"metodo_pago":"tarjeta","datos":{"numero":"4111111111111111","cvv":"123"}}'
curl "http://localhost:8000/library"
```

### Descuentos estacionales (excluyentes entre sí, como en Steam)

| Temporada | Fechas | Descuento | Alcance |
|---|---|---|---|
| Rebajas de Invierno | 22 dic – 5 ene | 30% | Todo el catálogo |
| Año Nuevo Lunar | 8 – 15 feb | 20% | Todo el catálogo |
| Rebajas de Verano | 25 jun – 9 jul | 25% | Todo el catálogo |
| Halloween | 27 oct – 1 nov | 40% | Solo etiqueta `terror` |
| Rebajas de Otoño | 21 – 28 nov | 20% | Todo el catálogo |

Nunca se aplican dos a la vez. Sobre el precio ya rebajado se aplica el IVA
(19%), y en los DLC hay un 10% adicional si el usuario ya tiene el juego base.

---

## Los 5 patrones

| # | Patrón | Categoría | Archivo | Problema del diagnóstico que resuelve |
|---|---|---|---|---|
| 1 | Singleton | Creacional | `despues/db.py` | P2 · 13 conexiones sueltas, cobro no atómico |
| 2 | Factory Method | Creacional | `despues/factories.py` | P3, P4 · if/elif al crear productos |
| 3 | Decorator | Estructural | `despues/precios.py` | P5 · regla de precios triplicada y divergida |
| 4 | Strategy | Comportamiento | `despues/pagos.py` | P6 · if/elif de medios de pago |
| 5 | Observer | Comportamiento | `despues/eventos.py` | P7 · checkout de 8 pasos con efectos cableados |

El detalle de roles GoF, justificación y alternativas descartadas está en
[`docs/PATRONES.md`](docs/PATRONES.md).

---

## El defecto que hace visible el refactor

Con fecha 2026-12-25 (Rebajas de Invierno), la versión **antes**:

```
/games    ->  99 960
/cart     ->  84 000   <-- le falta el IVA
/checkout ->  99 960   <-- el usuario paga algo distinto de lo que vio
```

No es un ejemplo forzado: es la consecuencia de tener la misma regla escrita en
`antes/tienda.py:165`, `:264` y `:359`. La versión **después** usa una sola
cadena de decoradores para los tres endpoints, así que no pueden divergir.
`python demo.py` lo ejecuta y lo imprime.

---

## Estructura

```
mini-steam/
├── demo.py                 Comparación ejecutable antes/después
├── requirements.txt
├── antes/
│   ├── modelos.py          Producto polivalente con campo `tipo`
│   ├── tienda.py           Clase Dios: 419 líneas, 13 métodos
│   └── main.py             Rutas con reglas de negocio adentro
├── despues/
│   ├── db.py               PATRÓN 1 · Singleton
│   ├── modelos.py          Jerarquía Producto → Juego / DLC
│   ├── factories.py        PATRÓN 2 · Factory Method
│   ├── precios.py          PATRÓN 3 · Decorator + calendario de promociones
│   ├── pagos.py            PATRÓN 4 · Strategy
│   ├── eventos.py          PATRÓN 5 · Observer
│   ├── repositorios.py     Aísla el SQL (no es patrón GoF)
│   ├── servicios.py        Casos de uso: orquesta los 5 patrones
│   ├── esquemas.py         Entrada Pydantic
│   └── main.py             Rutas delgadas
├── tests/
│   ├── test_dominio.py     27 pruebas: una sección por patrón
│   ├── test_api.py         15 pruebas de los endpoints
│   └── correr_pruebas.py   Ejecutor sin dependencias
└── docs/
    ├── DIAGNOSTICO.md      8 problemas con archivo:línea
    ├── PATRONES.md         Roles GoF, justificación y alternativas
    └── SUSTENTACION.md     Guion de 12 min + banco de preguntas
```

## Limitaciones conocidas

Simplificaciones deliberadas de un proyecto didáctico:

- Sin autenticación: el usuario es siempre `USUARIO_ID = 1`.
- Pagos simulados, sin pasarela real.
- Correo simulado: se escribe al log y a la tabla `notificaciones`.
- Dinero en `float`; en producción debería ser `Decimal`.
- SQLite en archivo único, sin migraciones.
