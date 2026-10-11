from pathlib import Path
from playwright.sync_api import Page, expect
from helpers.core.auth import login



def test_dashboard_contable(page: Page, base_url: str, credentials: dict):
    login(page, base_url, "/finanzas/accounting-dashboard/", credentials)

    expect(page.locator("h1")).to_contain_text("Dashboard de Carga Contable")
    expect(page.get_by_role("article")).to_match_aria_snapshot("- text:  Mes\n- textbox \" Mes\": /\\d+-\\d+/\n- button \" Consultar\"")
    page.get_by_role("button", name=" Consultar").click()

