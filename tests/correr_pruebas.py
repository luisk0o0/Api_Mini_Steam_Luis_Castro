"""Ejecutor minimo de las pruebas de dominio, por si no hay pytest instalado.

    python -m tests.correr_pruebas

Las pruebas de API (`tests/test_api.py`) si requieren pytest + fastapi:

    pytest -q
"""

import traceback

from tests import test_dominio


def main():
    pruebas = [(nombre, getattr(test_dominio, nombre))
               for nombre in dir(test_dominio) if nombre.startswith("test_")]
    fallidas = []
    for nombre, funcion in pruebas:
        try:
            funcion()
            print("  ok   %s" % nombre)
        except Exception:
            fallidas.append(nombre)
            print("  FALLA %s" % nombre)
            traceback.print_exc()
    print("\n%d pruebas, %d fallidas" % (len(pruebas), len(fallidas)))
    return 1 if fallidas else 0


if __name__ == "__main__":
    raise SystemExit(main())
