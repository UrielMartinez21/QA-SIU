from pathlib import Path
from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str, credentials: dict) -> None:
    """Hace login y deja la pantalla de carga contable abierta.

    El parametro next= hace que, al enviar el login, el servidor redirija
    directamente a la pantalla de carga contable. Por eso NO se hace un
    segundo goto (provocaria un net::ERR_ABORTED al interrumpir esa
    redireccion en curso).
    """
    page.goto(f"{base_url}/usuarios/login/?next=/finanzas/accounting-dashboard/")
    page.get_by_role("textbox", name="Matrícula").fill(credentials["user"])
    page.get_by_role("textbox", name="Contraseña").fill(credentials["password"])
    page.get_by_role("button", name="Entrar").click()

    # Esperar a que la redireccion del login termine en la pantalla destino
    # y a que la pagina cargue por completo (no solo que cambie la URL).
    page.wait_for_url("**/finanzas/accounting-dashboard/")
    page.wait_for_load_state("networkidle")


def test_dashboard_contable(page: Page, base_url: str, credentials: dict):
    _login(page, base_url, credentials)

    expect(page.locator("h1")).to_contain_text("Dashboard de Carga Contable")
    expect(page.get_by_role("article")).to_match_aria_snapshot("- text:  Mes\n- textbox \" Mes\": /\\d+-\\d+/\n- button \" Consultar\"")
    page.get_by_role("button", name=" Consultar").click()

