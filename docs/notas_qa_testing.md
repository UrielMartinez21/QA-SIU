# Notas: Automatización de QA y Testing

> Fecha: 2026-09-15
> Rama: `feature/1774627924-accounting-system`
> Contexto: Optimizar el trabajo de QA, que hoy valida **todo manual** (subir Excel,
> revisar cada error, revisar pantallas) sin conocimientos de código.

---

## 1. Problema a resolver

- QA ejecuta validación **manual end-to-end en el navegador**: sube un Excel,
  verifica que aparezcan todos los mensajes de error, revisa las pantallas nuevas.
- QA **no sabe programar**.
- Es trabajo repetitivo y determinístico que se repite en cada release → candidato
  ideal para automatizar.
- Objetivo: reducir el esfuerzo manual sin obligar a QA a aprender a programar.

---

## 2. Cómo se testean apps web Django profesionalmente

### La pirámide de testing
Muchas pruebas rápidas y baratas abajo; pocas lentas y caras arriba.

```
        /\
       /  \      E2E (navegador)              ← pocas, lentas, frágiles
      /____\
     /      \    Integración (API/vistas/DB)  ← moderadas
    /________\
   /          \  Unitarias (funciones/modelos) ← muchas, rápidas
  /____________\
```

### Nivel 1 — Unitarias (la base, lo más numeroso)
- Prueban funciones, métodos de modelos, validadores de forma aislada. Milisegundos por test.
- **Herramientas:** test runner nativo de Django (`django.test.TestCase`) o **pytest-django**
  (popular por sintaxis limpia, fixtures y parametrización).
- **En este proyecto:** funciones `validate_excel_*` de `helpers.py` y
  `get_monthly_trial_balance` de `services.py`.

### Nivel 2 — Integración (vistas, endpoints, BD)
- Prueban piezas trabajando juntas: una vista responde bien, un endpoint devuelve el
  JSON correcto, una query real contra la BD funciona.
- **Herramientas:**
  - `django.test.Client` para simular peticiones a vistas (login, POST de formularios,
    subida de archivos con `SimpleUploadedFile`).
  - **DRF `APITestCase`** para endpoints de API REST (este proyecto usa DRF).
  - Django crea una **BD de prueba temporal** automáticamente y la destruye al final.
- **Detalle clave del proyecto:** la BD es **Oracle y requiere VPN**. Por eso
  `test_accounting_system.py` usa `SimpleTestCase` (evita crear/migrar BD). Lo
  profesional sería configurar una **BD de test ligera** (SQLite/Postgres en
  contenedor) para no depender de Oracle.

### Nivel 3 — End-to-End (navegador real, la cima)
- Prueban la app como el usuario: abren navegador, hacen clic, suben archivos,
  verifican la pantalla. Las más realistas pero lentas y frágiles → hacer **pocas**
  (solo flujos críticos).
- **Herramientas modernas:**
  - **Playwright** (la más recomendada hoy): rápida, estable, esperas automáticas,
    graba scripts, soporta Python.
  - **Cypress** (muy popular, JS/TS).
  - **Selenium** (clásico, aún usado en empresas grandes, más verboso).

### Cómo trabajan los equipos profesionales
1. **Desarrolladores** escriben unitarias y de integración junto con el código
   (a veces TDD). Corren en cada commit.
2. **QA** se enfoca en:
   - Diseñar **casos de prueba** (su expertise: escenarios, casos borde, datos
     maliciosos). Sigue siendo humano y valioso.
   - Automatizar flujos E2E repetitivos (Playwright/Cypress). El **grabador de
     Playwright** (`codegen`) permite generar scripts sin escribir código.
   - **Testing exploratorio manual**: usabilidad, cosas visuales, casos nuevos.
3. **CI/CD**: todas las pruebas corren solas en cada push/PR (GitHub Actions,
   GitLab CI, Jenkins). Si algo falla, no se mergea. Esto es lo que realmente
   "optimiza QA".
4. **Datos de prueba controlados**: factories (`factory_boy`) o fixtures, más
   archivos de prueba versionados (los Excel de cada escenario).
5. **Cobertura** (`coverage.py`) con un mínimo acordado (ej. 80%).

---

## 3. Mapeo: lo que QA hace hoy → dónde debería ir

| Qué prueban hoy manual | Dónde debería ir | Herramienta |
|------------------------|------------------|-------------|
| "Subo Excel sin la hoja correcta → ¿sale el error?" | Unitaria o integración | `TestCase` / `APITestCase` |
| "Cada error de validación del Excel" | Unitaria (mayoría) | pytest-django / `TestCase` |
| "El flujo completo desde la pantalla funciona" | E2E (pocos casos) | Playwright |
| "La tabla muestra 12 meses, sin TOTAL, con tolerancia" | Integración + 1 E2E | `Client` / Playwright |
| Casos nuevos, usabilidad | Manual exploratorio | Humano |

**Idea central:** empujar las pruebas **hacia abajo** en la pirámide (más unitarias,
menos E2E), correrlas en **CI automáticamente**, y dejar a QA el diseño de casos y lo
exploratorio. La mayoría de lo que QA hace a mano (validar cada error del Excel)
debería ser unitario/integración: rápido y sin navegador. Solo unos pocos flujos
completos justifican E2E.

---

## 4. Estado actual del testing en el proyecto (hallazgos)

- **Framework real:** Django `TestCase`/`SimpleTestCase` nativo (unittest), NO pytest
  (aunque las reglas del repo mencionan pytest, el código usa Django unittest).
- **Ejecución:** `python manage.py test ... --settings=settings.migr`.
- **`SimpleTestCase` a propósito** para evitar tocar Oracle (que requiere VPN).
- **Linter:** ruff (`line-length = 120`, `target-version = "py313"`). No hay coverage
  configurado en `pyproject.toml`.
- **Ya existe** `src/SistemaV2/finanzas/tests/test_accounting_system.py`, pero está
  **todo comentado**. Cubre solo las validaciones del Excel (reglas de carga), NO
  cubre `get_monthly_trial_balance` (reglas 3-8 del requerimiento).
- El archivo de tests usa el patrón: `SimpleTestCase` + `unittest.mock`
  (`patch`, `MagicMock`) + `pandas` para construir DataFrames de prueba.

### Archivos relevantes de finanzas
| Archivo | Qué contiene |
|---------|--------------|
| `src/SistemaV2/finanzas/services/services.py` | `get_monthly_trial_balance` (cálculo), `_persist_balance_records` (carga Excel) |
| `src/SistemaV2/finanzas/helpers.py` | Funciones `validate_excel_*`, `validate_accounting_account_*` |
| `src/SistemaV2/finanzas/models.py` | `AccountingBalanceRecord`, `AccountingUploadAttempt` |
| `src/SistemaV2/finanzas/views.py` | `accounting_file_upload` (pantalla de carga), `monthly_trial_balance` |
| `src/SistemaV2/finanzas/tests/test_accounting_system.py` | Tests de validación del Excel (COMENTADOS) |
| `src/api/v1/finanzas/views.py` | Endpoint API `monthly_trial_balance` |
| `src/api/v1/finanzas/serializers.py` | `MonthlyTrialBalanceSerializer` (solo valida params de entrada) |
| `src/templates/sistemav2/finanzas/monthly_trial_balance.html` | Template de la tabla |
| `src/static_desarrollo/sistemav2/js/finanzas/monthly_trial_balance.js` | JS de la tabla (tarjetas, buscador, filtro, export) |

---

## 5. Opciones de herramienta E2E (para el flujo de subir Excel)

**Opción A — Playwright (recomendada)**
- Generador por grabación (`playwright codegen`): QA hace clic y sube el Excel,
  Playwright **genera el script solo**. QA no escribe código.
- Rápido y estable; maneja bien uploads (`setInputFiles`) y esperas automáticas.
- Soporta Python (encaja con Django) o JS/TS.
- Reportes con capturas y video del fallo (útil para documentar bugs).

**Opción B — Cypress**
- Popular, buena experiencia visual. Pero es JS/TS y el manejo de uploads y
  multi-pestaña es menos cómodo que Playwright.

**Opción C — Katalon / low-code**
- Para QA totalmente no técnico ("grabar y reproducir" guiado). Contra: externas,
  a veces de pago, menos flexibles.

**Elección para este caso:** Playwright con `codegen` en Python (mejor balance para
Django + QA no-code + subida de Excel).

### Cómo se vería el flujo E2E optimizado
1. Carpeta de **Excels de prueba** versionados (uno por escenario: sin hoja
   `BASE_BAL_ACUM`, columna faltante, cuenta mal formada, carga válida, etc.).
2. Cada escenario = un test: "sube este Excel → espera este mensaje / éxito".
3. QA **graba** con `playwright codegen` navegando la pantalla real.
4. Se corren todos con un comando → reporte con capturas.
5. En CI, corren solos en cada cambio.

---

## 6. Recomendación / plan sugerido

**Combinar dos niveles (no solo E2E):**
- **Unitarios** de `validate_excel_*` (helpers.py) → rápidos, sin navegador, cubren
  "qué error se dispara con qué dato". `test_accounting_system.py` ya está pensado
  para esto (solo hay que descomentar/ampliar).
- **E2E** (Playwright) → pocos, para confirmar que la pantalla muestra los errores y
  el flujo completo funciona.

**Orden propuesto:**
1. **(Valor inmediato, cero infra nueva)** Reactivar y ampliar los tests unitarios de
   validación del Excel que ya existen comentados en `test_accounting_system.py`.
2. **(En paralelo, PoC)** Montar Playwright con 1 test de ejemplo que suba un Excel a
   la pantalla de carga contable y valide un mensaje, para evaluar el flujo de UI.
3. **(Apoyo a QA)** Documento corto en español explicando cómo grabar un caso con
   `playwright codegen` y agregarlo, sin saber programar.
4. **(Futuro)** Tests unitarios data-driven de `get_monthly_trial_balance` para las
   reglas 3-8 (QA aporta la tabla de casos: país, año, acumulados, movimientos
   esperados). Detecta regresiones como el cambio movimiento↔acumulado.

---

## 7. Preguntas abiertas / pendientes para mañana

- [ ] ¿`settings.migr` (o `settings.seed`) permite correr `manage.py test` **sin VPN**?
      Con `SimpleTestCase` debería, pero confirmar. Para tests de integración con BD
      real habría que resolver la dependencia de Oracle/VPN o configurar BD de test ligera.
- [ ] ¿Hay entorno para levantar el front **localmente** o un ambiente de QA con URL
      accesible (tipo `siu-seed.scalahed.com`) para correr el E2E? Esto define si
      Playwright corre en local o contra ambiente desplegado.
- [ ] ¿QA va a **grabar** sus propios casos (Playwright codegen) o preferimos que dev
      escriba los tests a partir de los casos que QA diseña?
- [ ] ¿Existe pipeline de CI (GitHub Actions/GitLab CI/Jenkins) donde enganchar la
      suite para que corra automáticamente?
- [ ] Decidir si se adopta **pytest-django** o se mantiene el runner nativo de Django
      (el proyecto hoy usa el nativo).

---

## 8. Contexto de entorno (recordatorio)

- BD **Oracle**, requiere **VPN**.
- Intérprete Python del venv de Windows: `venv/Scripts/python.exe` (venv sobre WSL).
- Settings de desarrollo: `settings.seed` y `settings.migr`.
- Convención del repo: **código en inglés, documentación en español**.
- Los archivos de código usan finales de línea **CRLF** (relevante al editar con
  herramientas que asumen LF).

---

## 9. Playwright a detalle (qué es, cómo se usa, qué saber antes)

### 9.1 Qué es
- Herramienta de **automatización de navegadores** creada por Microsoft.
- Controla Chrome, Firefox y Safari/WebKit por código para simular a un usuario real:
  abrir página, clic, escribir, subir archivos, verificar resultados.
- Uso principal: **pruebas end-to-end (E2E)**. En este proyecto: entrar a la pantalla
  de carga contable, subir un Excel, verificar que salgan los mensajes de error.

### 9.2 Por qué se recomienda (vs. Selenium)
- **Auto-waiting**: espera automáticamente a que el elemento exista y sea clickeable
  antes de actuar → elimina los `sleep()` frágiles de Selenium.
- **Multi-navegador**: el mismo test corre en Chromium, Firefox y WebKit.
- **Generador por grabación (`codegen`)**: grabas acciones y genera el código solo
  (clave para QA sin código).
- **Rápido y aislado**: cada test corre en un contexto limpio (como incógnito).
- **Buen debugging**: screenshots, video y "trace" para ver paso a paso qué falló.
- Soporta **Python** (encaja con Django) y JavaScript/TypeScript.

### 9.3 Qué saber ANTES de usarlo

**Conocimientos técnicos base:**
- **Nociones de HTML/CSS**: entender qué es un elemento, `id`, `class`, atributo
  (para localizar elementos). No hace falta programar CSS, solo leer la estructura.
- **Selectores / locators**: EL concepto central. Un locator es cómo le dices a
  Playwright "este elemento específico" (por texto, `id`, rol de accesibilidad, etc.).
  La calidad de los tests depende de elegir buenos locators.
- **Nociones básicas de Python o JS**: para editar/entender los scripts. Con `codegen`
  se puede empezar sin escribir nada, pero ayuda saber lo mínimo.
- **Línea de comandos**: instalar y correr se hace desde la terminal.

**Conceptos propios de Playwright:**
- **`page`**: una pestaña del navegador. Casi todo se hace sobre `page`
  (`page.goto(url)`, `page.click(...)`).
- **Acciones**: `click`, `fill` (escribir en input), `set_input_files` (subir archivo),
  `select_option`.
- **Assertions (`expect()`)**: verificar que algo se cumple (ej. que un texto sea
  visible). Si no se cumple, el test falla. Tiene auto-waiting.
- **Auto-waiting**: no se ponen esperas manuales; Playwright espera solo.

**Requisitos de entorno (crítico para este proyecto):**
- **URL donde corra la app**: local (`localhost:8000`) o ambiente QA
  (`siu-seed.scalahed.com`). Playwright necesita algo que abrir.
- **Autenticación**: la pantalla de carga requiere login + permisos; el test debe
  resolver el login primero. Playwright puede **guardar la sesión** para no loguearse
  en cada test.
- **Datos de prueba**: los Excel de cada escenario deben existir como archivos
  versionados.
- **VPN/backend**: si la app depende de Oracle+VPN, el ambiente donde corra el E2E
  debe tener ese acceso. (Ver preguntas abiertas, sección 7.)

### 9.4 Cómo se usa — flujo típico

**Instalación (una vez):**
```bash
pip install playwright
playwright install        # descarga los navegadores
```

**Opción A: Grabar con codegen (ideal para QA sin código):**
```bash
playwright codegen http://localhost:8000/finanzas/carga-contable/
```
Se abre el navegador y una ventana que **va escribiendo el código conforme haces
clic**. QA navega normal (login, seleccionar país, subir Excel) y al terminar copia el
código generado. Luego se limpia y se le agregan las verificaciones.

**Opción B: Escribir el test (ejemplo conceptual para el flujo de subir Excel):**
```python
from playwright.sync_api import sync_playwright, expect

def test_subir_excel_sin_hoja_correcta():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # 1. Ir a la pantalla (asumiendo login ya resuelto)
        page.goto("http://localhost:8000/finanzas/carga-contable/")

        # 2. Subir un Excel de prueba con estructura inválida
        page.set_input_files("input[type=file]", "tests/fixtures/excel_sin_hoja.xlsx")

        # 3. Hacer clic en el botón de cargar
        page.get_by_role("button", name="Cargar").click()

        # 4. Verificar que aparezca el mensaje de error esperado
        expect(page.get_by_text("La pestaña BASE_BAL_ACUM es obligatoria")).to_be_visible()

        browser.close()
```
Cada escenario que QA prueba a mano se vuelve una función como esta.

**Correr los tests:**
```bash
pytest                    # con el plugin pytest-playwright
# o
playwright test           # en la versión JS/TS
```
Sale un reporte; si algo falla, hay screenshot/video/trace para diagnosticar.

### 9.5 Qué NO es / limitaciones
- **No reemplaza a QA humano**: no evalúa usabilidad, estética ni descubre casos
  nuevos. Automatiza lo repetitivo; el juicio sigue siendo humano.
- **No sustituye pruebas unitarias**: E2E es lento y frágil. La mayoría de
  validaciones del Excel conviene probarlas en nivel unitario (más rápido) y dejar
  E2E solo para flujos críticos.
- **Requiere mantenimiento**: si cambia la UI (texto/posición de un botón), los tests
  pueden romperse y hay que actualizarlos.
- **Necesita infraestructura**: ambiente corriendo, datos y, idealmente, CI.

### 9.6 Ruta de aprendizaje sugerida
1. Instalar Playwright y correr un `codegen` contra cualquier web pública para ver
   cómo graba.
2. Entender **locators** (el 80% del valor está aquí) — doc oficial de locators.
3. Grabar un flujo real de la app (login + una pantalla).
4. Aprender `expect()` para agregar verificaciones.
5. Organizar tests y datos de prueba en el repo.
6. Enganchar a CI.

> NOTA: Los ejemplos de código y URLs (`/finanzas/carga-contable/`, nombre del botón
> "Cargar", mensaje de error) son **conceptuales/ilustrativos**. Falta verificar la
> URL real, el selector del input de archivo, el texto real del botón y los mensajes
> de error exactos contra el template y el JS antes de escribir los tests reales.

---

## 10. Perfiles de QA que necesita el proyecto

> Contexto: hoy hay **1 perfil** (QA manual/funcional que valida a mano y no programa)
> + un dev Python senior que puede cubrir la automatización. La meta es operar como
> las grandes empresas sin necesariamente contratar un equipo de QA completo.

### Aclaración sobre la pirámide
La pirámide **no** busca que *todas* las pruebas sean unitarias, sino una **proporción**:
muchas unitarias (base), algunas de integración (medio), pocas E2E (cima). Cada nivel
prueba algo que los otros no pueden. Una unitaria confirma que `validate_excel_*`
devuelve el error correcto, pero solo una E2E confirma que ese error **llega a la
pantalla** que ve el usuario. La meta correcta: empujar hacia abajo lo determinístico
y barato, reservar E2E para los pocos flujos críticos.

### Perfiles priorizados por el riesgo del proyecto

#### 1. QA Manual / Funcional — YA EXISTE, es la base
- Diseña los **casos de prueba** del sistema contable de `finanzas/`: cada escenario
  de Excel inválido (sin hoja `BASE_BAL_ACUM`, columna faltante, cuenta mal formada,
  tolerancias, 12 meses sin TOTAL).
- Aporta la **tabla de casos multi-país** que alimenta los tests (país, año,
  acumulados, movimientos esperados en `get_monthly_trial_balance`).
- Hace **testing exploratorio**: usabilidad, cosas visuales, casos no previstos.
- Valida en el **ambiente QA** los flujos completos antes de pasar a producción.
- Su valor es el **criterio humano**: no se automatiza.

#### 2. QA Automation / SDET — EL QUE FALTA (lo cubre el dev senior)
- Convierte los casos que diseña el QA manual en **pruebas automatizadas** (unitarias + E2E).
- Reactiva y amplía los tests de `test_accounting_system.py` (hoy comentados).
- Escribe y mantiene las **E2E con Playwright** para los flujos críticos de carga contable.
- Construye y cuida el **pipeline de CI**.
- Le enseña al QA manual a **grabar casos con `playwright codegen`** sin programar.
- En este caso lo asume el propio dev senior — no requiere contratación nueva de entrada.

#### 3. QA de API / Backend — NECESARIO por la API REST propia (`api/v1/`)
- Prueba endpoints de `api/v1/` (finanzas, escolares, dlocal_payouts, autoenrollment):
  códigos de estado, estructura del JSON, validación de parámetros.
- Valida **autenticación y API keys** (`api/authentication.py`, modelo `ApiKey`,
  `api/middleware.py`).
- Verifica **contratos** con integraciones externas (`external_apis`, `hubspot`, `banner`).
- Puede ser el mismo SDET al inicio; usa `APITestCase` de DRF y Postman.

#### 4. QA de Seguridad — NECESARIO por pagos + datos personales multi-país
- Valida autorización en `api/v1/`: que un usuario no acceda a datos de otro
  país/institución.
- Revisa el manejo seguro de las **pasarelas de pago** (`Simoba/`: dlocal, ebanx,
  bitpay, bancolombia...): que no se manipulen montos, que los webhooks estén verificados.
- Verifica la protección de **datos personales por jurisdicción** (avisos de privacidad
  por país → obligaciones legales distintas).
- El proyecto ya tiene herramientas (Snyk en el pipeline, `.snyk` en `requirements/`).
  Puede ser un rol parcial/consultivo, no full-time.

#### 5. QA de Performance — OPCIONAL, menor prioridad
- Mide `get_monthly_trial_balance` (agregaciones contra Oracle) bajo volumen.
- Detecta N+1 queries en vistas de `escolares/` y `finanzas/` con muchos registros.
- Mide tiempos de la carga masiva de Excel (`_persist_balance_records`).
- Posponible hasta que haya problemas concretos de rendimiento.

### Resumen

| Perfil | ¿Necesario? | Quién lo cubre |
|--------|-------------|----------------|
| QA Manual / Funcional | Sí — ya existe | QA actual |
| QA Automation / SDET | Sí — el mayor salto | Dev senior |
| QA de API / Backend | Sí | Dev senior, al inicio |
| QA de Seguridad | Sí (pagos + multi-país) | Dev senior / apoyo puntual |
| QA de Performance | Opcional | Más adelante |

**Conclusión:** con **2 personas** (el QA manual diseñando casos + el dev senior
automatizando y sosteniendo el CI) se cubren los primeros 3 perfiles, que es lo mínimo
para arrancar. Seguridad y performance se suman según el riesgo lo exija. No se necesita
contratar un equipo de QA completo.

### Perfiles vs. niveles de la pirámide (NO es un mapeo 1 a 1)

Un error común es pensar que los 5 perfiles equivalen a los escalones de la pirámide
("perfil 1 = base, perfil 5 = cima"). **No es así.** Son dos ejes distintos:

- La **pirámide** clasifica **tipos de prueba** (unitaria / integración / E2E) por su
  proporción y costo → guía la *estrategia*.
- Los **perfiles** son **personas con habilidades** (quién hace el trabajo) → *ejecutan*
  esa estrategia.

Un mismo perfil toca varios niveles, y un mismo nivel lo cubren varios perfiles:

| Nivel de la pirámide | Perfil(es) que lo cubren |
|----------------------|--------------------------|
| **Unitarias** (base, muchas) | SDET/Automation (las escribe) + QA Manual (diseña los casos) |
| **Integración** (medio) | SDET/Automation + QA de API/Backend |
| **E2E** (cima, pocas) | SDET/Automation (escribe) + QA Manual (graba con codegen, valida) |
| **Transversal** (cruza todos) | QA de Seguridad, QA de Performance |

Notas clave:
- El **SDET aparece en los tres niveles**: es quien construye la automatización sin
  importar el nivel.
- **Seguridad y Performance NO son un nivel** de la pirámide clásica; son pruebas
  **transversales** (pueden ser unitarias, de integración o E2E). Por eso no encajan
  como "el escalón de arriba".

**Conclusión sobre la relación:** los perfiles no *son* la pirámide, pero sí la
*respetan*. El principio (mucho abajo, poco arriba) ordena el esfuerzo de todos: la
mayor parte del trabajo va a unitarias/integración (barato, rápido, en CI) y muy poco
a E2E. La realidad de las grandes empresas es **pocas personas, muchos niveles**: QA
manual diseña, SDET automatiza en todos los niveles, y seguridad/performance cruzan todo.
