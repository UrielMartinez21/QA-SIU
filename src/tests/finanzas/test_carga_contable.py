"""
Pruebas E2E de la pantalla de carga contable (finanzas/accounting-file-upload).

Usa las fixtures definidas en conftest.py:
- credentials: usuario y password del .env
- base_url: ambiente (local o migr)
"""

from pathlib import Path

from playwright.sync_api import Page, expect

# Carpeta con los Excel de prueba. Se resuelve relativa a ESTE archivo,
# para que funcione sin importar desde donde se ejecute pytest.
FIXTURES = Path(__file__).parents[2] / "fixtures" / "finanzas"


def _login(page: Page, base_url: str, credentials: dict) -> None:
    """Hace login y deja la pantalla de carga contable abierta.

    El parametro next= hace que, al enviar el login, el servidor redirija
    directamente a la pantalla de carga contable. Por eso NO se hace un
    segundo goto (provocaria un net::ERR_ABORTED al interrumpir esa
    redireccion en curso).
    """
    page.goto(f"{base_url}/usuarios/login/?next=/finanzas/accounting-file-upload/")
    page.get_by_role("textbox", name="Matrícula").fill(credentials["user"])
    page.get_by_role("textbox", name="Contraseña").fill(credentials["password"])
    page.get_by_role("button", name="Entrar").click()
    # Esperar a que la redireccion del login termine en la pantalla destino
    # y a que la pagina cargue por completo (no solo que cambie la URL).
    page.wait_for_url("**/finanzas/accounting-file-upload/")
    page.wait_for_load_state("networkidle")


def test_pantalla_carga_contable_carga_bien(page: Page, base_url: str, credentials: dict):
    """La pantalla de carga contable se muestra correctamente tras el login."""
    _login(page, base_url, credentials)

    # Margen amplio: tras el login la pagina puede tardar en renderizar.
    expect(page.get_by_role("heading", name="Carga Masivaa")).to_be_visible(timeout=15000)
    expect(page.locator("#fileInput")).to_be_attached()
    # El boton de subir arranca deshabilitado hasta elegir pais, mes y archivo.
    expect(page.get_by_role("button", name="Subir archivo")).to_be_disabled()


# def test_subir_excel_sin_hoja_correcta(page: Page, base_url: str, credentials: dict):
#     """Subir un Excel sin la pestana BASE_BAL_ACUM debe mostrar el error esperado.

#     Caso SEGURO contra migr: la validacion rechaza el archivo antes de persistir.
#     Requiere el fixture: fixtures/finanzas/excel_sin_hoja.xlsx
#     """
#     _login(page, base_url, credentials)

#     # Elegir pais y mes (la pantalla los pide antes de habilitar la subida).
#     page.locator("#countrySelect").select_option(index=1)
#     page.locator("#monthSelect").fill("2026-01")

#     # Subir el Excel de prueba con estructura invalida.
#     page.locator("#fileInput").set_input_files(str(FIXTURES / "excel_sin_hoja.xlsx"))
#     page.get_by_role("button", name="Subir archivo").click()

#     # Verificar el mensaje de error real (de helpers.py).
#     errores = page.locator("#validationErrorsSection")
#     expect(errores).to_be_visible()
#     expect(errores).to_contain_text("No se encontro la pestana obligatoria 'BASE_BAL_ACUM'.")
