"""
Configuracion compartida de pytest para las pruebas E2E.

Aqui viven las fixtures que usan todos los tests:
- Carga de variables de entorno desde .env
- Credenciales del usuario de pruebas
- URL base del ambiente (local o migr)
- (Opcional) reutilizacion de sesion con storage_state para no loguear cada vez
"""

import os

import pytest
from dotenv import load_dotenv

# Carga las variables definidas en .env (si el archivo existe).
load_dotenv()


@pytest.fixture(scope="session")
def base_url() -> str:
    """URL base del ambiente donde corren las pruebas.

    Se define con la variable de entorno E2E_BASE_URL. Por defecto usa local.
    Tambien se puede sobreescribir al ejecutar con el flag --base-url de pytest.
    """
    return os.environ.get("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def credentials() -> dict:
    """Credenciales del usuario de pruebas, leidas de variables de entorno.

    NUNCA se escriben en el codigo. Se definen en el archivo .env (no versionado)
    o exportandolas en la terminal:
        export E2E_USER="tu_matricula"
        export E2E_PASSWORD="tu_password"
    """
    user = os.environ.get("E2E_USER")
    password = os.environ.get("E2E_PASSWORD")

    if not user or not password:
        pytest.fail(
            "Faltan credenciales. Define E2E_USER y E2E_PASSWORD en un archivo .env "
            "o exportalas en la terminal. Ver .env.example."
        )

    return {"user": user, "password": password}


# ---------------------------------------------------------------------------
# OPCIONAL: reutilizar la sesion del login para no autenticarse en cada test.
#
# 1. Graba la sesion una vez:
#      playwright codegen http://localhost:8000/usuarios/login/ --save-storage=auth.json
# 2. Descomenta la fixture de abajo. Playwright abrira cada test ya logueado.
# ---------------------------------------------------------------------------
# @pytest.fixture(scope="session")
# def browser_context_args(browser_context_args):
#     return {**browser_context_args, "storage_state": "auth.json"}
