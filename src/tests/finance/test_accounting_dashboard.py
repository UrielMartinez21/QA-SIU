"""
Pruebas E2E de la pantalla de dashboard contable (finanzas/accounting-dashboard).

Usa las fixtures definidas en conftest.py:
- credentials: usuario y password del .env
- base_url: ambiente (local o seed)
"""

from playwright.sync_api import Page, expect

from helpers.core.auth import login

# Ruta de la pantalla, reutilizada por todos los tests de este archivo.
DASHBOARD = "/finanzas/accounting-dashboard/"


def test_accounting_dashboard(page: Page, base_url: str, credentials: dict) -> None:
    """La pantalla de dashboard contable se muestra correctamente tras el login."""
    login(page, base_url, DASHBOARD, credentials)

    expect(page.locator("h1")).to_contain_text("Dashboard de Carga Contable")


def test_load_history(page: Page, base_url: str, credentials: dict) -> None:
    """Al consultar un mes, se muestran el historial de cargas y la bitacora."""
    login(page, base_url, DASHBOARD, credentials)

    page.get_by_role("textbox", name=" Mes").fill("2026-09")
    page.get_by_role("button", name=" Consultar").click()

    expect(page.locator("#dashboardConfig")).to_contain_text("Historial de cargas")
    expect(page.get_by_role("article")).to_contain_text("Bitacora de movimientos")


def test_error_modal(page: Page, base_url: str, credentials: dict) -> None:
    """El detalle de una carga fallida abre el modal de errores de validacion.

    NOTA: depende de una fila concreta ("Latam ... Fallido ... Samuel Antonio
    Mejia") que debe existir en el ambiente. Si esos datos cambian o se
    eliminan, el test fallara. Considera un ambiente/datos controlados.
    """
    login(page, base_url, DASHBOARD, credentials)

    page.get_by_role("textbox", name=" Mes").fill("2026-09")
    page.get_by_role("button", name=" Consultar").click()

    page.get_by_role(
        "row",
        name="Latam 9 Fallido 25/9/2026 09:41 p.m. Samuel Antonio Mejia  Ver detalles",
    ).get_by_role("button").click()

    expect(page.locator("#errorsModalLabel")).to_contain_text("Errores de validación")

    page.get_by_text("Cerrar", exact=True).click()
    expect(page.locator("#errorsModalLabel")).not_to_be_visible()


def test_download_report(page: Page, base_url: str, credentials: dict) -> None:
    """El boton Descargar genera la descarga de un archivo."""
    login(page, base_url, DASHBOARD, credentials)

    page.get_by_role("textbox", name=" Mes").fill("2026-09")
    page.get_by_role("button", name=" Consultar").click()

    # La descarga se abre en una pestana nueva (popup) que a su vez dispara
    # el evento de descarga. Esperamos ambos.
    with page.expect_download() as download_info:
        with page.expect_popup() as popup_info:
            page.get_by_role("button", name=" Descargar").click()
        popup = popup_info.value
    download = download_info.value

    # Verificar que efectivamente llego un archivo con nombre.
    assert download.suggested_filename, "La descarga no tiene nombre de archivo"

    popup.close()
