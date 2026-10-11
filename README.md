# QA — Pruebas E2E con Playwright

Suite de pruebas end-to-end **aislada del proyecto `siu`**: automatiza lo que QA valida
manualmente en el navegador (empezando por la carga contable de finanzas), sin tocar el
código de la aplicación.

- ¿Nuevo en Playwright? → lee `docs/guia_playwright_e2e.md` (de 0 a experto).
- ¿Solo quieres correr o agregar tests aquí? → este README.

## Requisitos

- Python 3.13 (el proyecto ya trae un `venv/` con todo instalado).
- Acceso al ambiente a probar (ver [Ambientes](#ambientes)).

## Estructura

```
QA/
├── README.md                      # Este archivo (operación del proyecto)
├── requirements.txt               # Dependencias
├── pytest.ini                     # Config + flags de evidencia (fijos)
├── .env.example                   # Plantilla de variables (copiar a .env)
├── .gitignore                     # Ignora evidencia, auth.json, .env, venv
├── docs/
│   ├── guia_playwright_e2e.md     # Aprender Playwright de 0 a experto
│   └── notas_qa_testing.md        # Estrategia de testing del proyecto
└── src/
    ├── conftest.py                # Fixtures compartidas (base_url, credentials, sesión)
    ├── helpers/<module>/            # Tests E2E por módulo
    ├── tests/<module>/            # Tests E2E por módulo
    │   └── finance/test_carga_contable.py
    └── fixtures/<module>/         # Datos de prueba (Excel), por módulo
        └── finance/README.md     # Qué Excel colocar
```

La evidencia de fallos (screenshot/video/trace) se genera en `test-results/` (ignorada por git).

## Puesta en marcha (una vez)

```bash
# 1. Activar el venv
venv\Scripts\activate                # Windows
# source venv/bin/activate           # Unix/Mac

# 2. Si el venv no existiera, crearlo e instalar:
#    python -m venv venv && venv\Scripts\activate
#    pip install -r requirements.txt && playwright install

# 3. Credenciales: copiar la plantilla y rellenar
copy .env.example .env               # Windows  (cp en Unix/Mac)
# editar .env con tu matrícula, password y el ambiente (E2E_BASE_URL)
```

El archivo `.env` es obligatorio: si faltan `E2E_USER` / `E2E_PASSWORD`, los tests fallan
con un mensaje claro. Nunca se versiona (está en `.gitignore`).

## Ambientes

El ambiente se define con `E2E_BASE_URL` en el `.env`, o al vuelo con `--base-url`:

| Ambiente | URL | VPN |
|----------|-----|-----|
| Local | `http://localhost:8000` | según backend |
| Seed (desplegado) | `https://siu-seed.scalahed.com:8023` | no (público) |

```bash
pytest --base-url https://siu-seed.scalahed.com:8023   # sobreescribe el .env
```

## Correr las pruebas

Ejecuta siempre desde la carpeta `QA/` (donde está `pytest.ini`).

```bash
pytest                                 # todo, headless
pytest --headed                        # viendo el navegador
pytest --headed --slowmo 500           # headed y lento (depurar)

pytest src/tests/finanzas/             # solo un módulo
pytest src/tests/finanzas/test_carga_contable.py                 # solo un archivo
pytest src/tests/finanzas/test_carga_contable.py::test_pantalla_carga_contable_carga_bien  # solo un test
pytest -k "sin_hoja"                   # tests cuyo nombre contiene "sin_hoja"

pytest --browser firefox               # otro navegador (chromium por defecto)
```

Los flags de evidencia ya están fijos en `pytest.ini`. Si un test falla, revisa
`test-results/` y abre el trace (lo más útil para diagnosticar):

```bash
playwright show-trace test-results/.../trace.zip
```

## Agregar pruebas

1. Crea `src/tests/<modulo>/test_<algo>.py`.
2. Si necesita datos, agrégalos en `src/fixtures/<modulo>/`.
3. Reutiliza las fixtures `page`, `base_url` y `credentials` (ver un test existente).
4. Para generar el borrador rápido, graba con el Inspector y límpialo:
   ver `docs/guia_playwright_e2e.md`.

> ⚠️ **Datos reales:** los casos de *error* son seguros en cualquier ambiente (se rechazan
> antes de persistir). El caso de *carga válida* escribe en la BD Oracle; córrelo solo en
> un ambiente desechable.

## Referencia

- Aprender Playwright (0 → experto): `docs/guia_playwright_e2e.md`
- Estrategia de testing del proyecto: `docs/notas_qa_testing.md`
