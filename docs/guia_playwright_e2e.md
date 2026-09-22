# Playwright de 0 a experto — Guía de pruebas E2E

Guía de aprendizaje completa, de los fundamentos al nivel avanzado. No cubre la operación
de este repositorio (comandos del día a día, estructura, `.env`): eso está en `../README.md`.

**Índice**
1. [Qué es y cuándo usarlo](#1-qué-es-y-cuándo-usarlo)
2. [Modelo mental](#2-modelo-mental)
3. [Instalación](#3-instalación)
4. [Grabar con `codegen`](#4-grabar-con-codegen)
5. [Convertir lo grabado en un test](#5-convertir-lo-grabado-en-un-test)
6. [Locators (lo más importante)](#6-locators-lo-más-importante)
7. [Acciones](#7-acciones)
8. [Esperas y auto-waiting](#8-esperas-y-auto-waiting)
9. [Verificaciones con `expect`](#9-verificaciones-con-expect)
10. [Depurar: screenshot, video y trace](#10-depurar-screenshot-video-y-trace)
11. [Autenticación reutilizable](#11-autenticación-reutilizable)
12. [Organizar una suite](#12-organizar-una-suite)
13. [Seguridad](#13-seguridad)
14. [Temas avanzados](#14-temas-avanzados)
15. [CI/CD](#15-cicd)
16. [Errores comunes](#16-errores-comunes)
17. [Ruta de aprendizaje](#17-ruta-de-aprendizaje)

---

## 1. Qué es y cuándo usarlo

Playwright (de Microsoft) automatiza navegadores (Chromium, Firefox, WebKit) por código:
abre páginas, hace clic, escribe, sube archivos y verifica resultados como un usuario real.

Se usa para **pruebas end-to-end (E2E)**: la cima de la pirámide de testing. Son las más
realistas pero lentas y frágiles → conviene tener **pocas**, solo para flujos críticos.
La mayoría de validaciones deben ser unitarias/integración (ver `notas_qa_testing.md`).

**Por qué Playwright y no Selenium:** auto-waiting (sin `sleep` frágiles), multi-navegador,
grabador (`codegen`), contexto aislado por test, y trace para depurar.

## 2. Modelo mental

Todo test es el mismo ciclo: **navegar → localizar → actuar → verificar**.

```python
page.goto("/login")                                  # navegar
page.get_by_role("textbox", name="Usuario")          # localizar
        .fill("ana")                                 # actuar
expect(page.get_by_text("Bienvenida")).to_be_visible()  # verificar
```

`page` = una pestaña del navegador. Casi todo cuelga de ella.

## 3. Instalación

```bash
pip install pytest-playwright   # Playwright + integración con pytest
playwright install              # descarga los navegadores
```

`pytest-playwright` aporta la fixture `page` (un navegador limpio por test) y flags como
`--headed`, `--browser`, `--tracing`.

## 4. Grabar con `codegen`

El Inspector graba tus clics y genera el código. Es la forma más rápida de empezar y no
requiere saber programar.

```bash
playwright codegen https://playwright.dev    # practicar con una web pública
playwright codegen <URL>                     # apuntar a tu pantalla
playwright codegen -b firefox <URL>          # otro navegador (chromium/firefox/webkit)
playwright codegen <URL> -o grabado.py       # volcar lo grabado a un archivo
```

Se abren el **navegador** y el **Inspector**. Barra del Inspector:

| Botón | Función |
|-------|---------|
| ● Record | activa/desactiva la grabación |
| Pick locator | pasas el mouse sobre un elemento y te da su mejor locator |
| Assert visibility | genera `expect(...).to_be_visible()` |
| Assert text | genera `expect(...).to_contain_text("...")` |
| Assert snapshot | captura una instantánea (aria) del elemento |

El **selector de lenguaje** está en el panel del código (no en la barra): elige
**Python → Pytest**. Clave: el `codegen` graba *acciones*; las *verificaciones* las marcas
tú con los botones Assert (o las escribes después).

## 5. Convertir lo grabado en un test

El `codegen` da un borrador con andamiaje. Hay que limpiarlo.

**Crudo (lo que genera):**

```python
from playwright.sync_api import Playwright, sync_playwright


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://.../login/?next=/destino/")
    page.get_by_role("textbox", name="Usuario").click()
    page.get_by_role("textbox", name="Usuario").fill("ana")
    page.get_by_role("button", name="Entrar").click()
    page.goto("https://.../destino/")
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
```

**Limpio (test de pytest):**

```python
import os
from playwright.sync_api import Page, expect

BASE_URL = os.environ["E2E_BASE_URL"]


def test_destino_carga(page: Page):
    page.goto(f"{BASE_URL}/login/?next=/destino/")
    page.get_by_role("textbox", name="Usuario").fill(os.environ["E2E_USER"])
    page.get_by_role("button", name="Entrar").click()

    page.wait_for_url("**/destino/")            # dejar que el login redirija
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="Destino")).to_be_visible()
```

Transformaciones:

1. **Quitar el andamiaje** (`run()`, `sync_playwright()`, `launch()`, `close()`): lo da la fixture `page`.
2. **Volverlo `test_...(page)`** (pytest descubre lo que empieza con `test_`).
3. **Credenciales/URL a variables de entorno** (ver [Seguridad](#13-seguridad)).
4. **Quitar `.click()` redundantes** antes de cada `.fill()` (llenar ya da foco).
5. **Evitar la doble navegación**: un segundo `goto` tras el login lo interrumpe y causa
   `net::ERR_ABORTED`; usar `wait_for_url` + `wait_for_load_state`.
6. **Agregar el `expect`**: el `codegen` no lo pone solo.

## 6. Locators (lo más importante)

Un locator identifica un elemento. El 80% de la calidad de un test está aquí. De mejor a peor:

```python
# 1. Por rol + nombre accesible (PREFERIDO: como lo percibe el usuario)
page.get_by_role("button", name="Guardar")
page.get_by_role("textbox", name="Correo")

# 2. Por texto visible
page.get_by_text("Bienvenida")

# 3. Por label / placeholder / test-id
page.get_by_label("Contraseña")
page.get_by_placeholder("tu@correo.com")
page.get_by_test_id("submit")          # si el HTML tiene data-testid

# 4. Por id (estable si no cambia)
page.locator("#fileInput")

# 5. EVITAR: CSS frágil dependiente de la maquetación
page.locator("div > div:nth-child(3) > span")
```

**Refinar y encadenar:**

```python
page.get_by_role("row", name="Ana").get_by_role("button", name="Editar")
page.get_by_role("listitem").filter(has_text="Pendiente")
page.get_by_role("button").nth(0)      # primero; .first / .last también
```

Regla: prefiere lo que el **usuario ve** (rol, texto, label). Sobrevive a cambios de CSS.

## 7. Acciones

```python
page.goto(url)
locator.click()
locator.fill("texto")                  # limpia y escribe (inputs)
locator.type("texto", delay=100)       # tecla por tecla (si hace falta)
locator.press("Enter")
locator.check() / locator.uncheck()    # checkboxes
locator.select_option("valor")         # <select> por valor
locator.select_option(index=1)         # por posición
locator.select_option(label="México")  # por texto visible
locator.set_input_files("ruta.xlsx")   # subir archivo(s)
locator.hover()
page.keyboard.press("Escape")
```

## 8. Esperas y auto-waiting

Playwright **espera solo** a que el elemento exista, sea visible y esté habilitado antes de
actuar. **No uses `time.sleep()`** — es la causa nº1 de tests frágiles.

Cuando necesites esperar algo explícito:

```python
page.wait_for_url("**/destino/")               # a que cambie la URL
page.wait_for_load_state("networkidle")         # a que la red se calme
page.wait_for_selector("#tabla")                # a que aparezca un elemento
locator.wait_for(state="visible")               # estado de un locator
```

`expect()` (siguiente sección) también tiene auto-waiting con reintentos: es la forma
preferida de "esperar a que algo sea verdad".

## 9. Verificaciones con `expect`

`expect()` reintenta hasta cumplirse o agotar el timeout. Es lo que convierte un script en
una prueba.

```python
expect(locator).to_be_visible()
expect(locator).to_be_hidden()
expect(locator).to_be_enabled() / to_be_disabled()
expect(locator).to_have_text("exacto")
expect(locator).to_contain_text("parcial")
expect(locator).to_have_value("valor")          # inputs
expect(locator).to_have_count(3)
expect(page).to_have_url(re.compile(r"/destino/"))
expect(page).to_have_title("Mi App")

expect(locator).to_be_visible(timeout=15000)     # timeout puntual (ms)
expect(locator).not_to_be_visible()              # negación
```

## 10. Depurar: screenshot, video y trace

Tres tipos de evidencia (flags de pytest):

```bash
pytest --screenshot=only-on-failure    # imagen del momento del fallo
pytest --video=retain-on-failure       # video de la ejecución
pytest --tracing=retain-on-failure     # TRACE: paso a paso interactivo (el mejor)
```

Valores: `only-on-failure` / `retain-on-failure` (recomendados), `on` (siempre), `off`.
Todo queda en `test-results/`. Abrir un trace:

```bash
playwright show-trace test-results/.../trace.zip
```

El trace muestra la línea de tiempo, un **snapshot del DOM** inspeccionable en cada paso,
consola y red. Es la mejor herramienta para "¿por qué no encontró el elemento?".

Otras ayudas:

```bash
pytest --headed --slowmo 500           # ver el navegador, lento
PWDEBUG=1 pytest                        # abre el Inspector paso a paso (debug interactivo)
```

> Si el fallo ocurre durante una navegación (sin página cargada) o con `--headed`, puede
> no generarse la imagen aunque sí el video y el trace. El trace ya trae los snapshots.

## 11. Autenticación reutilizable

Loguearse en cada test es lento. Graba la sesión una vez y reutilízala:

```bash
playwright codegen <URL>/login/ --save-storage=auth.json
```

En `conftest.py`:

```python
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "storage_state": "auth.json"}
```

Todos los tests arrancan ya logueados. (Alternativa avanzada: un fixture que haga login por
API una vez y guarde el `storage_state`.)

## 12. Organizar una suite

**Un archivo por pantalla/funcionalidad**, varias funciones dentro. Ni un archivo por test
ni todo en uno.

```
src/tests/
├── finanzas/
│   ├── test_carga_contable.py     # todos los escenarios de esa pantalla
│   └── test_balanza_mensual.py    # otra pantalla
└── escolares/
    └── test_inscripcion.py
```

- Mismo flujo/pantalla → mismo archivo (funciones separadas, o clases `class TestX:`).
- Otra pantalla → otro archivo. Otro módulo → otra carpeta.
- Helpers compartidos (p. ej. `_login`) al inicio del archivo o en `conftest.py`.
- Datos de prueba (Excel, JSON) versionados aparte, en `fixtures/`.

**Fixtures** (`conftest.py`) para lo repetido: credenciales, URL base, sesión, datos.

```python
@pytest.fixture
def usuario_logueado(page, base_url, credentials):
    # login una vez por test que la pida
    ...
    return page
```

**Parametrizar** para muchos casos con el mismo cuerpo:

```python
import pytest

@pytest.mark.parametrize("archivo,mensaje", [
    ("excel_sin_hoja.xlsx", "No se encontro la pestana obligatoria"),
    ("excel_columna.xlsx", "La columna obligatoria"),
])
def test_excel_invalido(page, archivo, mensaje):
    ...
```

## 13. Seguridad

- **NUNCA** hardcodear usuario/contraseña: el `codegen` los graba en texto plano. Sácalos a
  variables de entorno (un `.env` ignorado por git).
  ```python
  import os
  user = os.environ["E2E_USER"]
  ```
- No subir `auth.json` (contiene la sesión) ni `.env` al repositorio.
- Cuidado al correr contra ambientes compartidos: acciones que **persisten datos** (una
  carga válida, un alta) afectan a otros. Prefiere casos de *error* o ambientes desechables.

## 14. Temas avanzados

- **Multi-navegador:** `pytest --browser firefox --browser webkit`. El mismo test corre en
  los tres motores sin cambios.
- **Paralelismo:** `pip install pytest-xdist` y `pytest -n auto` para correr en paralelo.
- **Interceptar red / mocks:** `page.route("**/api/**", handler)` para simular respuestas.
- **Descargas:** `with page.expect_download() as d: ...` y `d.value.save_as(ruta)`.
- **Diálogos/alerts:** `page.on("dialog", lambda d: d.accept())`.
- **Múltiples pestañas:** `with context.expect_page() as p: ...`.
- **API testing:** `page.request.get(url)` / `post(...)` para pegar a endpoints sin UI
  (útil para preparar datos antes de un E2E).
- **Aria snapshots:** `expect(locator).to_match_aria_snapshot(...)` para verificar un bloque
  completo de una vez (frágil ante cambios; úsalo con criterio).

## 15. CI/CD

En un servidor no hay pantalla → siempre **headless**. Ejemplo con GitHub Actions:

```yaml
- uses: actions/setup-python@v5
  with: { python-version: "3.13" }
- run: pip install -r requirements.txt
- run: playwright install --with-deps
- run: pytest            # headless; evidencia en test-results/ si algo falla
  env:
    E2E_USER: ${{ secrets.E2E_USER }}
    E2E_PASSWORD: ${{ secrets.E2E_PASSWORD }}
    E2E_BASE_URL: ${{ vars.E2E_BASE_URL }}
```

Sube `test-results/` como artefacto para revisar traces de fallos. Las credenciales van en
*secrets*, nunca en el YAML.

## 16. Errores comunes

| Síntoma | Causa / solución |
|---------|------------------|
| `net::ERR_ABORTED` en un `goto` | Doble navegación (un `goto` interrumpe otra en curso). Usa `wait_for_url` en vez del segundo `goto`. |
| `element(s) not found` en `expect` | Locator mal escrito, o la página aún no cargó. Revisa el texto exacto (¡typos!) y agrega `wait_for_load_state`. |
| Test frágil (a veces pasa, a veces no) | Uso de `time.sleep()`. Cámbialo por auto-waiting / `expect`. |
| No se genera la imagen del fallo | El fallo fue en navegación o corriste `--headed`. Usa el trace. |
| Faltan credenciales | No existe `.env` o le faltan `E2E_USER` / `E2E_PASSWORD`. |
| Locator ambiguo (resuelve a varios) | Refina con `.filter()`, `.nth()`, o un rol/nombre más específico. |

## 17. Ruta de aprendizaje

1. Instala y corre `codegen` contra una web pública (secciones 3–4).
2. Graba un flujo real y límpialo a un test (5).
3. Domina **locators** (6) — es el 80% del valor.
4. Aprende `expect` y las esperas (8–9).
5. Aprende a leer el **trace** cuando algo falla (10).
6. Resuelve el login con `storage_state` (11).
7. Organiza la suite: fixtures, parametrización, un archivo por pantalla (12).
8. Avanzado: paralelismo, mocks, API testing (14) y engánchalo a CI (15).
