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


def pytest_configure(config):
    """Fija la salida de pytest-playwright a una ruta absoluta de la corrida.

    Asi el trace/video siempre quedan dentro de `reportes/<corrida>/` y no en un
    `test-results/` relativo al directorio desde donde se ejecute pytest.
    """
    config.option.output = str(_PW_OUTPUT_DIR)


def pytest_sessionfinish(session, exitstatus):
    """Limpia la carpeta de artefactos del plugin al terminar la corrida.

    Los traces de los tests fallidos ya se movieron junto a su .md, asi que esta
    carpeta temporal (`_playwright_artifacts/`) ya no aporta y se elimina para
    dejar `reportes/<corrida>/` limpia (solo .md, .png y _trace.zip).
    """
    if _PW_OUTPUT_DIR.exists():
        shutil.rmtree(_PW_OUTPUT_DIR, ignore_errors=True)


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
