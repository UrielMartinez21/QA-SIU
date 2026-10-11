from playwright.sync_api import Page


def login(page: Page, base_url: str, destination: str ,credentials: dict) -> None:
    """Hace login y deja abierta la pantalla indicada en `destination`. 
    Args:
        page: la pagina de Playwright.
        base_url: raiz del ambiente, ej. "https://siu-seed.scalahed.com:8023".
        destination: ruta a la que redirigir tras el login, ej.
            "/finanzas/accounting-file-upload/".
        credentials: dict con "user" y "password".

    El parametro next= hace que, al enviar el login, el servidor redirija
    directamente a `destination`. Por eso NO se hace un segundo goto
    (provocaria un net::ERR_ABORTED al interrumpir esa redireccion en curso).
    """

    page.goto(f"{base_url}/usuarios/login/?next={destination}")
    page.get_by_role("textbox", name="Matrícula").fill(credentials["user"])
    page.get_by_role("textbox", name="Contraseña").fill(credentials["password"])
    page.get_by_role("button", name="Entrar").click()

    # Esperar a que la redireccion del login termine en la pantalla destino
    # y a que la pagina cargue por completo (no solo que cambie la URL).
    page.wait_for_url(f"**{destination}")
    page.wait_for_load_state("networkidle")