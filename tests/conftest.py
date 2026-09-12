"""Configuracion de pytest.

Se apunta STEAM_DB a un archivo temporal ANTES de importar la aplicacion, para
que las pruebas nunca escriban sobre el `steam.db` de desarrollo.
"""

import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

os.environ.setdefault("STEAM_DB", os.path.join(tempfile.mkdtemp(), "pruebas.db"))
