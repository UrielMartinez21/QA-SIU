"""
Configuracion compartida de pytest para las pruebas E2E.

Aqui viven las fixtures que usan todos los tests:
- Carga de variables de entorno desde .env
- Credenciales del usuario de pruebas
- URL base del ambiente (local o migr)
- (Opcional) reutilizacion de sesion con storage_state para no loguear cada vez

Ademas, este archivo genera AUTOMATICAMENTE un documento de evidencia por cada
prueba ejecutada (pase o falle):
- Un archivo .md por prueba + una captura .png, agrupados en una carpeta por
  corrida con timestamp dentro de `reportes/`.
- Registra: que se probo, insumos usados, pasos ejecutados (automaticos),
  metricas (duracion, tiempo de carga, HTTP, peticiones, errores de consola) y
  el resultado obtenido.
"""

import datetime as _dt
import html as _html
import os
import shutil
from pathlib import Path

import pytest
from dotenv import load_dotenv
from slugify import slugify

# Carga las variables definidas en .env (si el archivo existe).
load_dotenv()

# Raiz del proyecto QA (carpeta que contiene pytest.ini), para resolver `reportes/`.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Carpeta de la corrida actual (se crea una vez por sesion de pytest).
_RUN_STAMP = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
_RUN_DIR = _PROJECT_ROOT / "reportes" / _RUN_STAMP

# Carpeta temporal donde pytest-playwright deja sus artefactos (trace/video/png).
# La fijamos a una ruta ABSOLUTA dentro de la corrida para no depender del CWD
# ni perder el trace. De aqui movemos el trace.zip al lado del .md cuando falla.
_PW_OUTPUT_DIR = _RUN_DIR / "_playwright_artifacts"

# Acumula el resumen de cada prueba de la corrida para construir el index.html
# navegable al terminar la sesion (ver _write_html_index). Cada entrada es un
# dict con: name, passed, duration, ambiente, navegador, md, png, trace.
_RUN_RESULTS: list[dict] = []


def pytest_configure(config):
    """Fija la salida de pytest-playwright a una ruta absoluta de la corrida.

    Asi el trace/video siempre quedan dentro de `reportes/<corrida>/` y no en un
    `test-results/` relativo al directorio desde donde se ejecute pytest.
    """
    config.option.output = str(_PW_OUTPUT_DIR)


def pytest_sessionfinish(session, exitstatus):
    """Cierra la corrida: genera el index.html y limpia los artefactos del plugin.

    1. Escribe un `index.html` navegable con el resumen de todas las pruebas de
       la corrida (enlaces al .md, a la captura y al trace de cada una).
    2. Borra la carpeta temporal `_playwright_artifacts/` (los traces de los
       tests fallidos ya se movieron junto a su .md), dejando
       `reportes/<corrida>/` limpia (solo index.html, .md, .png y _trace.zip).
    """
    # 1. Indice navegable de la corrida (solo si hubo pruebas con evidencia).
    if _RUN_RESULTS:
        try:
            _write_html_index()
        except Exception:
            # El index es un extra: si algo falla no debe tumbar la corrida.
            pass

    # 2. Limpieza de la carpeta temporal del plugin.
    if _PW_OUTPUT_DIR.exists():
        shutil.rmtree(_PW_OUTPUT_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def base_url(request) -> str:
    """URL base del ambiente donde corren las pruebas.

    Prioridad (de mayor a menor):
      1. Flag de linea de comandos --base-url (lo registra pytest-playwright).
      2. Variable de entorno E2E_BASE_URL (archivo .env).
      3. Valor por defecto local (http://localhost:8000).

    Asi el flag de consola SIEMPRE gana sobre el .env, que es lo que documenta
    el README. Ejemplo:
        python -m pytest --base-url https://siu-migr.scalahed.com:8023
    """
    # pytest-playwright registra la opcion --base-url; si no se paso, es None.
    cli_base_url = request.config.getoption("--base-url", default=None)
    if cli_base_url:
        return cli_base_url
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


# ===========================================================================
# DOCUMENTACION AUTOMATICA DE EVIDENCIA POR PRUEBA
# ===========================================================================


class _Recorder:
    """Acumula los datos de una prueba para construir su documento de evidencia.

    Se expone a los tests mediante la fixture `reporte` (opcional):
        def test_x(page, reporte):
            reporte.insumo("Archivo subido", "excel_sin_hoja.xlsx")
            reporte.dato("Pais", "Mexico")

    Los pasos ejecutados se capturan AUTOMATICAMENTE desde los eventos de
    Playwright (no hay que declararlos a mano).
    """

    def __init__(self) -> None:
        self.insumos: list[tuple[str, str]] = []
        self.datos: list[tuple[str, str]] = []
        self.pasos: list[str] = []
        self.descargas: list[str] = []
        self.console_errors: list[str] = []
        self.request_count: int = 0
        self.response_errors: int = 0
        self.main_status: str = "N/D"
        self.final_url: str = "N/D"

    # --- API publica para los tests (opcional) ---
    def insumo(self, nombre: str, valor: str) -> None:
        """Registra un insumo usado por la prueba (ej. un archivo subido)."""
        self.insumos.append((nombre, str(valor)))

    def dato(self, nombre: str, valor: str) -> None:
        """Registra un dato extra de contexto (ej. pais, mes, matricula)."""
        self.datos.append((nombre, str(valor)))

    def paso(self, descripcion: str) -> None:
        """Agrega un paso manual (por si se quiere complementar lo automatico)."""
        self.pasos.append(str(descripcion))


def _instrument_page(page, rec: "_Recorder") -> None:
    """Conecta listeners de Playwright para capturar pasos y metricas solos."""

    def _on_framenavigated(frame):
        # Solo el frame principal (la navegacion de la pagina, no iframes).
        if frame == page.main_frame:
            rec.pasos.append(f"Navegacion a {frame.url}")

    def _on_request(_request):
        rec.request_count += 1

    def _on_response(response):
        try:
            status = response.status
        except Exception:
            return
        if status >= 400:
            rec.response_errors += 1
        # El estado de la navegacion principal: primera respuesta del documento.
        if rec.main_status == "N/D" and response.url == page.url:
            rec.main_status = str(status)

    def _on_console(msg):
        if msg.type == "error":
            rec.console_errors.append(msg.text)

    def _on_download(download):
        name = download.suggested_filename
        rec.descargas.append(name)
        rec.pasos.append(f"Descarga de archivo: {name}")

    page.on("framenavigated", _on_framenavigated)
    page.on("request", _on_request)
    page.on("response", _on_response)
    page.on("console", _on_console)
    page.on("download", _on_download)


@pytest.fixture
def reporte(request) -> "_Recorder":
    """Fixture OPCIONAL: expone el grabador de evidencia a un test.

    Los tests que no la usen igual generan su documento (sin las secciones de
    insumos/datos). Si un test la pide, puede registrar insumos y datos extra.
    """
    rec: _Recorder = request.node._qa_recorder
    return rec


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    """Crea el grabador antes de cada test y lo cuelga del nodo."""
    item._qa_recorder = _Recorder()
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """Instrumenta la `page` (si el test la usa) justo antes de ejecutarlo."""
    rec: _Recorder = getattr(item, "_qa_recorder", None)
    page = item.funcargs.get("page") if hasattr(item, "funcargs") else None
    if rec is not None and page is not None:
        _instrument_page(page, rec)
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Genera el documento de evidencia de la prueba.

    - En la fase `call`: toma la captura y las metricas (la `page` sigue viva).
    - En la fase `teardown`: ya existe el `trace.zip` (lo escribe el plugin al
      cerrar el contexto), asi que lo movemos junto al .md y escribimos el reporte.
    """
    outcome = yield
    report = outcome.get_result()

    rec: _Recorder = getattr(item, "_qa_recorder", None)
    if rec is None:
        return

    # --- Fase CALL: capturar evidencia mientras la pagina sigue abierta ---
    if report.when == "call":
        page = item.funcargs.get("page") if hasattr(item, "funcargs") else None
        _RUN_DIR.mkdir(parents=True, exist_ok=True)
        screenshot_name = f"{item.name}.png"
        screenshot_rel = screenshot_name
        tiempo_carga = "N/D"

        if page is not None:
            try:
                page.screenshot(path=str(_RUN_DIR / screenshot_name), full_page=True)
            except Exception as exc:  # pagina ya cerrada u otro problema
                screenshot_rel = None
                rec.pasos.append(f"(No se pudo tomar captura: {exc})")

            try:
                rec.final_url = page.url
            except Exception:
                pass

            try:
                # Tiempo de carga de la pagina via Navigation Timing API.
                nav_ms = page.evaluate(
                    "() => { const n = performance.getEntriesByType('navigation')[0];"
                    " return n ? Math.round(n.duration) : null; }"
                )
                if nav_ms is not None:
                    tiempo_carga = f"{nav_ms / 1000:.2f} s"
            except Exception:
                pass
        else:
            screenshot_rel = None

        # Guardar lo capturado para usarlo al escribir el reporte en teardown.
        item._qa_call_report = report
        item._qa_screenshot_rel = screenshot_rel
        item._qa_tiempo_carga = tiempo_carga
        return

    # --- Fase TEARDOWN: el trace ya existe; moverlo y escribir el reporte ---
    if report.when == "teardown":
        call_report = getattr(item, "_qa_call_report", None)
        if call_report is None:
            return  # el test ni siquiera llego a ejecutarse

        trace_rel = _move_trace_if_failed(item, call_report)
        _write_report(
            item,
            call_report,
            rec,
            getattr(item, "_qa_screenshot_rel", None),
            getattr(item, "_qa_tiempo_carga", "N/D"),
            trace_rel,
        )


def _move_trace_if_failed(item, call_report) -> str | None:
    """Mueve el trace.zip del plugin a la carpeta de la corrida si el test fallo.

    Devuelve el nombre relativo del trace dentro de `reportes/<corrida>/`, o None.
    """
    if call_report.passed:
        return None

    # El plugin guarda en: <output>/<slugify(nodeid)>/trace.zip
    slug = slugify(item.nodeid)
    src = _PW_OUTPUT_DIR / slug / "trace.zip"
    if not src.exists():
        return None

    dest_name = f"{item.name}_trace.zip"
    dest = _RUN_DIR / dest_name
    try:
        shutil.move(str(src), str(dest))
    except Exception:
        # Si no se puede mover (p. ej. en uso), al menos intentar copiar.
        try:
            shutil.copy2(str(src), str(dest))
        except Exception:
            return None
    return dest_name


def _esc(valor) -> str:
    """Escapa texto para insertarlo de forma segura en cualquier HTML generado."""
    return _html.escape(str(valor), quote=True)


# CSS compartido entre el index.html y cada reporte .html de la corrida.
# Se centraliza aqui para que ambos tengan la misma identidad visual y para no
# duplicar estilos. Las llaves { } van dobladas {{ }} porque se inserta dentro
# de f-strings.
_SHARED_CSS = """
  :root {
    --bg: #eef1f6; --panel: #ffffff; --ink: #1b2330; --muted: #5b6672;
    --line: #e4e8ef; --line-soft: #eef1f5; --brand: #4f46e5; --brand-ink: #e0e7ff;
    --ok-bg: #dcfce7; --ok-ink: #15803d; --fail-bg: #fee2e2; --fail-ink: #b91c1c;
    --link: #4338ca; --shadow: 0 1px 2px rgba(16,24,40,.06), 0 8px 24px rgba(16,24,40,.06);
  }
  * { box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, Roboto, sans-serif;
    margin: 0; padding: 0 0 3rem; background: var(--bg); color: var(--ink);
    line-height: 1.5;
  }
  .wrap { max-width: 980px; margin: 0 auto; padding: 0 1.5rem; }
  header.hero {
    background: linear-gradient(120deg, #4f46e5 0%, #7c3aed 55%, #a855f7 100%);
    color: #fff; padding: 2rem 0 2.25rem; margin-bottom: -1.25rem;
    box-shadow: var(--shadow);
  }
  header.hero .wrap { display: flex; flex-direction: column; gap: .35rem; }
  header.hero .eyebrow {
    font-size: .72rem; text-transform: uppercase; letter-spacing: .12em;
    color: var(--brand-ink); font-weight: 600;
  }
  header.hero h1 { font-size: 1.55rem; margin: 0; font-weight: 700; }
  header.hero .meta { color: #ddd6fe; font-size: .85rem; margin-top: .15rem; }
  header.hero .meta b { color: #fff; font-weight: 600; }
  .panel {
    background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
    box-shadow: var(--shadow); padding: 1.25rem 1.4rem; margin-top: 1.25rem;
  }
  .panel h2 {
    font-size: .95rem; margin: 0 0 .9rem; text-transform: uppercase;
    letter-spacing: .04em; color: var(--muted);
  }
  .cards { display: flex; flex-wrap: wrap; gap: 1rem; }
  .card {
    flex: 1 1 140px; background: var(--panel); border: 1px solid var(--line);
    border-radius: 14px; padding: 1.1rem 1.25rem; box-shadow: var(--shadow);
  }
  .card .n { font-size: 1.9rem; font-weight: 800; line-height: 1; }
  .card .l {
    font-size: .74rem; color: var(--muted); text-transform: uppercase;
    letter-spacing: .05em; margin-top: .4rem; font-weight: 600;
  }
  .card.ok .n { color: var(--ok-ink); }
  .card.fail .n { color: var(--fail-ink); }
  .card.brand .n { color: var(--brand); }
  table { width: 100%; border-collapse: collapse; }
  th, td {
    text-align: left; padding: .75rem .85rem; border-bottom: 1px solid var(--line-soft);
    font-size: .9rem; vertical-align: top;
  }
  th {
    font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
    color: var(--muted); font-weight: 700;
  }
  tbody tr { transition: background .12s ease; }
  tbody tr:hover { background: #f7f8fc; }
  tr:last-child td { border-bottom: none; }
  td.name { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85rem; }
  .kv td:first-child { color: var(--muted); font-weight: 600; width: 34%; }
  .badge {
    display: inline-block; padding: .2rem .65rem; border-radius: 999px;
    font-size: .75rem; font-weight: 700; letter-spacing: .02em;
  }
  .badge.ok { background: var(--ok-bg); color: var(--ok-ink); }
  .badge.fail { background: var(--fail-bg); color: var(--fail-ink); }
  a { color: var(--link); text-decoration: none; font-weight: 500; }
  a:hover { text-decoration: underline; }
  .links a { margin-right: .1rem; }
  .sep { color: var(--line); margin: 0 .35rem; }
  ol, ul { margin: 0; padding-left: 1.25rem; }
  li { margin: .2rem 0; }
  .shot { max-width: 100%; border: 1px solid var(--line); border-radius: 10px; margin-top: .5rem; }
  pre {
    background: #0f172a; color: #e2e8f0; padding: 1rem; border-radius: 10px;
    overflow-x: auto; font-size: .82rem; line-height: 1.45;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin: .5rem 0 0;
  }
  .back { display: inline-block; margin-top: 1.25rem; font-size: .85rem; }
  .empty { color: var(--muted); font-style: italic; }
"""


def _html_page(title: str, body: str) -> str:
    """Envuelve un cuerpo HTML en un documento completo con el CSS compartido."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>{_SHARED_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{body}\n"
        "</body>\n</html>\n"
    )


def _write_report_html(item, report, rec: "_Recorder", screenshot_rel, tiempo_carga,
                       base_url_val, browser_val, que_se_probo, archivo_prueba,
                       estado, ahora, trace_rel=None) -> str:
    """Escribe un reporte .html formateado (legible en navegador) para una prueba.

    Convierte la misma informacion del .md a una pagina con estilo: encabezado
    con badge de estado, tablas de metadatos/metricas, pasos, captura embebida y
    el error (si fallo) en un bloque legible. Devuelve el nombre del archivo.
    """
    passed = report.passed
    estado_cls = "ok" if passed else "fail"
    estado_txt = "PASÓ" if passed else "FALLÓ"

    b: list[str] = []
    b.append('<header class="hero"><div class="wrap">')
    b.append('<span class="eyebrow">Reporte de prueba E2E</span>')
    b.append(f"<h1>{_esc(item.name)}</h1>")
    b.append(
        f'<div class="meta"><span class="badge {estado_cls}">{estado_txt}</span>'
        f" &nbsp; <b>{_esc(ahora)}</b> · {_esc(archivo_prueba)}</div>"
    )
    b.append("</div></header>")

    b.append('<div class="wrap">')

    # --- Metadatos ---
    b.append('<div class="panel"><h2>Datos de la prueba</h2>')
    b.append('<table class="kv"><tbody>')
    b.append(f"<tr><td>Resultado</td><td>{estado}</td></tr>")
    b.append(f"<tr><td>Fecha/hora</td><td>{_esc(ahora)}</td></tr>")
    b.append(f"<tr><td>Ambiente</td><td>{_esc(base_url_val)}</td></tr>")
    b.append(f"<tr><td>Navegador</td><td>{_esc(browser_val)}</td></tr>")
    b.append(f"<tr><td>Archivo de prueba</td><td>{_esc(archivo_prueba)}</td></tr>")
    b.append(f"<tr><td>URL final</td><td>{_esc(rec.final_url)}</td></tr>")
    b.append("</tbody></table></div>")

    # --- Que se probo ---
    b.append('<div class="panel"><h2>Qué se probó</h2>')
    b.append(f"<p>{_esc(que_se_probo).replace(chr(10), '<br>')}</p></div>")

    # --- Insumos ---
    if rec.insumos or rec.datos or rec.descargas:
        b.append('<div class="panel"><h2>Insumos utilizados</h2><ul>')
        for nombre, valor in rec.insumos:
            b.append(f"<li>{_esc(nombre)}: {_esc(valor)}</li>")
        for nombre, valor in rec.datos:
            b.append(f"<li>{_esc(nombre)}: {_esc(valor)}</li>")
        for nombre in rec.descargas:
            b.append(f"<li>Archivo descargado: {_esc(nombre)}</li>")
        b.append("</ul></div>")

    # --- Pasos ---
    b.append('<div class="panel"><h2>Pasos ejecutados</h2>')
    if rec.pasos:
        b.append("<ol>")
        for paso in rec.pasos:
            b.append(f"<li>{_esc(paso)}</li>")
        b.append("</ol>")
    else:
        b.append('<p class="empty">No se registraron navegaciones automáticas.</p>')
    b.append("</div>")

    # --- Metricas ---
    b.append('<div class="panel"><h2>Métricas</h2><table class="kv"><tbody>')
    b.append(f"<tr><td>Duración total</td><td>{report.duration:.2f} s</td></tr>")
    b.append(f"<tr><td>Tiempo de carga de página</td><td>{_esc(tiempo_carga)}</td></tr>")
    b.append(f"<tr><td>Código HTTP principal</td><td>{_esc(rec.main_status)}</td></tr>")
    b.append(
        f"<tr><td>Peticiones de red</td><td>{rec.request_count} "
        f"({rec.response_errors} con error)</td></tr>"
    )
    b.append(f"<tr><td>Errores de consola JS</td><td>{len(rec.console_errors)}</td></tr>")
    b.append("</tbody></table></div>")

    # --- Resultado / error ---
    b.append('<div class="panel"><h2>Resultado obtenido</h2>')
    if passed:
        b.append("<p>La prueba terminó correctamente (passed).</p>")
    else:
        b.append("<p>La prueba falló (failed). Detalle del error:</p>")
        b.append(f"<pre>{_esc(report.longrepr)}</pre>")
    b.append("</div>")

    # --- Errores de consola ---
    if rec.console_errors:
        b.append('<div class="panel"><h2>Errores de consola detectados</h2><ul>')
        for err in rec.console_errors:
            b.append(f"<li>{_esc(err)}</li>")
        b.append("</ul></div>")

    # --- Evidencia ---
    b.append('<div class="panel"><h2>Evidencia</h2>')
    if screenshot_rel:
        b.append(f'<img class="shot" src="{_esc(screenshot_rel)}" alt="captura de la prueba">')
    else:
        b.append('<p class="empty">No se pudo capturar screenshot.</p>')
    if trace_rel:
        b.append(
            f"<p>Trace de Playwright: <code>{_esc(trace_rel)}</code><br>"
            f"Para abrirlo: <code>playwright show-trace reportes/{_esc(_RUN_STAMP)}/{_esc(trace_rel)}</code></p>"
        )
    b.append("</div>")

    b.append('<a class="back" href="index.html">← Volver al índice de la corrida</a>')
    b.append("</div>")

    out_name = f"{item.name}.html"
    (_RUN_DIR / out_name).write_text(_html_page(f"Reporte · {item.name}", "\n".join(b)), encoding="utf-8")
    return out_name


def _write_report(item, report, rec: "_Recorder", screenshot_rel, tiempo_carga, trace_rel=None) -> None:
    """Escribe el archivo .md de evidencia para una prueba."""
    passed = report.passed
    estado = "✅ PASÓ" if passed else "❌ FALLÓ"
    ahora = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Metadatos del ambiente/navegador desde las fixtures del test, si existen.
    base_url_val = item.funcargs.get("base_url", "N/D") if hasattr(item, "funcargs") else "N/D"
    browser_val = "N/D"
    try:
        page = item.funcargs.get("page")
        if page is not None:
            browser_val = page.context.browser.browser_type.name
    except Exception:
        pass

    # "Que se probo": docstring de la funcion de prueba.
    doc = (item.function.__doc__ or "").strip() if hasattr(item, "function") else ""
    que_se_probo = doc.splitlines()[0].strip() if doc else "(sin descripcion)"
    if doc and len(doc.splitlines()) > 1:
        que_se_probo = doc  # usar el docstring completo si tiene varias lineas

    archivo_prueba = os.path.relpath(str(item.fspath), str(_PROJECT_ROOT))

    lines: list[str] = []
    lines.append(f"# Caso de prueba: {item.name}")
    lines.append("")
    lines.append("| Campo | Valor |")
    lines.append("|-------|-------|")
    lines.append(f"| Resultado | {estado} |")
    lines.append(f"| Fecha/hora | {ahora} |")
    lines.append(f"| Ambiente | {base_url_val} |")
    lines.append(f"| Navegador | {browser_val} |")
    lines.append(f"| Archivo de prueba | {archivo_prueba} |")
    lines.append(f"| URL final | {rec.final_url} |")
    lines.append("")

    lines.append("## Qué se probó")
    lines.append(que_se_probo)
    lines.append("")

    if rec.insumos or rec.datos:
        lines.append("## Insumos utilizados")
        for nombre, valor in rec.insumos:
            lines.append(f"- {nombre}: {valor}")
        for nombre, valor in rec.datos:
            lines.append(f"- {nombre}: {valor}")
        if rec.descargas:
            for nombre in rec.descargas:
                lines.append(f"- Archivo descargado: {nombre}")
        lines.append("")
    elif rec.descargas:
        lines.append("## Insumos utilizados")
        for nombre in rec.descargas:
            lines.append(f"- Archivo descargado: {nombre}")
        lines.append("")

    lines.append("## Pasos ejecutados")
    if rec.pasos:
        for i, paso in enumerate(rec.pasos, start=1):
            lines.append(f"{i}. {paso}")
    else:
        lines.append("(no se registraron navegaciones automaticas)")
    lines.append("")

    lines.append("## Métricas")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Duración total | {report.duration:.2f} s |")
    lines.append(f"| Tiempo de carga de página | {tiempo_carga} |")
    lines.append(f"| Código HTTP principal | {rec.main_status} |")
    lines.append(f"| Peticiones de red | {rec.request_count} ({rec.response_errors} con error) |")
    lines.append(f"| Errores de consola JS | {len(rec.console_errors)} |")
    lines.append("")

    lines.append("## Resultado obtenido")
    if passed:
        lines.append("La prueba terminó correctamente (passed).")
    else:
        lines.append("La prueba falló (failed). Detalle del error:")
        lines.append("")
        lines.append("```")
        lines.append(str(report.longrepr))
        lines.append("```")
    lines.append("")

    if rec.console_errors:
        lines.append("## Errores de consola detectados")
        for err in rec.console_errors:
            lines.append(f"- {err}")
        lines.append("")

    lines.append("## Evidencia")
    if screenshot_rel:
        lines.append(f"![captura]({screenshot_rel})")
    else:
        lines.append("(no se pudo capturar screenshot)")
    if trace_rel:
        lines.append("")
        lines.append(f"- Trace de Playwright: `{trace_rel}`")
        lines.append(f"  - Para abrirlo: `playwright show-trace reportes/{_RUN_STAMP}/{trace_rel}`")
    lines.append("")

    out_file = _RUN_DIR / f"{item.name}.md"
    out_file.write_text("\n".join(lines), encoding="utf-8")

    # Version HTML del mismo reporte (legible en navegador, no "como codigo").
    # Es la que enlaza el index; el .md se conserva para leer en editor/GitHub.
    html_name = _write_report_html(
        item, report, rec, screenshot_rel, tiempo_carga,
        base_url_val, browser_val, que_se_probo, archivo_prueba,
        estado, ahora, trace_rel,
    )

    # Registrar la prueba para el index.html navegable de la corrida.
    _RUN_RESULTS.append(
        {
            "name": item.name,
            "passed": passed,
            "duration": report.duration,
            "ambiente": str(base_url_val),
            "navegador": browser_val,
            "html": html_name,
            "md": out_file.name,
            "png": screenshot_rel,
            "trace": trace_rel,
        }
    )

# ===========================================================================
# INDICE HTML NAVEGABLE DE LA CORRIDA
# ===========================================================================


def _write_html_index() -> None:
    """Genera `reportes/<corrida>/index.html` con el resumen de la corrida.

    Es una vista navegable (una tabla) de todas las pruebas ejecutadas, con
    enlaces a su reporte .md, su captura .png y su trace .zip cuando existen.
    Da visibilidad rapida: cuantas pasaron/fallaron, cuanto duraron y el acceso
    directo a la evidencia de cada una, sin abrir los .md uno por uno.
    """
    total = len(_RUN_RESULTS)
    pasaron = sum(1 for r in _RUN_RESULTS if r["passed"])
    fallaron = total - pasaron
    duracion_total = sum(r["duration"] for r in _RUN_RESULTS)

    # Ambiente: normalmente es el mismo para toda la corrida; mostramos el
    # primero no vacio como referencia.
    ambiente = next((r["ambiente"] for r in _RUN_RESULTS if r["ambiente"] not in ("", "N/D")), "N/D")

    filas: list[str] = []
    for r in _RUN_RESULTS:
        estado_cls = "ok" if r["passed"] else "fail"
        estado_txt = "PASÓ" if r["passed"] else "FALLÓ"

        # El enlace principal apunta al reporte .html (legible). El .md queda
        # como enlace secundario. Captura y trace solo si existen.
        reporte_href = r.get("html") or r["md"]
        enlaces: list[str] = [f'<a href="{_esc(reporte_href)}">Ver reporte</a>']
        if r.get("md"):
            enlaces.append(f'<a href="{_esc(r["md"])}">MD</a>')
        if r["png"]:
            enlaces.append(f'<a href="{_esc(r["png"])}">Captura</a>')
        if r["trace"]:
            enlaces.append(f'<a href="{_esc(r["trace"])}">Trace</a>')
        evidencia = '<span class="sep">·</span>'.join(enlaces)

        filas.append(
            '<tr>'
            f'<td><span class="badge {estado_cls}">{estado_txt}</span></td>'
            f'<td class="name">{_esc(r["name"])}</td>'
            f'<td>{r["duration"]:.2f} s</td>'
            f'<td>{_esc(r["navegador"])}</td>'
            f'<td class="links">{evidencia}</td>'
            "</tr>"
        )

    generado = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tasa = f"{(pasaron / total * 100):.0f}%" if total else "—"

    body = f"""<header class="hero"><div class="wrap">
    <span class="eyebrow">Resumen de corrida E2E</span>
    <h1>Reporte de pruebas</h1>
    <div class="meta">Corrida <b>{_esc(_RUN_STAMP)}</b> · Ambiente <b>{_esc(ambiente)}</b> · Generado {_esc(generado)}</div>
  </div></header>
  <div class="wrap">
    <div class="cards">
      <div class="card brand"><div class="n">{total}</div><div class="l">Pruebas</div></div>
      <div class="card ok"><div class="n">{pasaron}</div><div class="l">Pasaron</div></div>
      <div class="card fail"><div class="n">{fallaron}</div><div class="l">Fallaron</div></div>
      <div class="card"><div class="n">{tasa}</div><div class="l">Tasa de éxito</div></div>
      <div class="card"><div class="n">{duracion_total:.1f} s</div><div class="l">Duración</div></div>
    </div>
    <div class="panel">
      <h2>Detalle de pruebas</h2>
      <table>
        <thead>
          <tr><th>Resultado</th><th>Prueba</th><th>Duración</th><th>Navegador</th><th>Evidencia</th></tr>
        </thead>
        <tbody>
          {"".join(filas)}
        </tbody>
      </table>
    </div>
  </div>"""

    (_RUN_DIR / "index.html").write_text(_html_page(f"Reporte de corrida · {_RUN_STAMP}", body), encoding="utf-8")
