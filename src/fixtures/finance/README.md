# Fixtures de finanzas — Excel de prueba

Coloca aquí los archivos Excel que usan las pruebas E2E de carga contable.
**No se generan por código**; son datos de prueba que debes crear/versionar a mano.

Cada archivo representa un escenario que hoy QA valida manualmente:

| Archivo | Escenario | Resultado esperado |
|---------|-----------|--------------------|
| `excel_sin_hoja.xlsx` | Excel sin la pestaña `BASE_BAL_ACUM` | Error: "No se encontro la pestana obligatoria 'BASE_BAL_ACUM'." |
| `excel_columna_faltante.xlsx` | Falta una columna (CODIGO/DESCRIPCION/SALDO) | Error: "La columna obligatoria '...' no se encontro." |
| `excel_pestana_extra.xlsx` | Tiene pestañas adicionales | Error: "El archivo contiene pestanas adicionales no permitidas: ..." |
| `excel_no_mayusculas.xlsx` | Contenido en minúsculas | Error: "... el valor '...' no esta en mayusculas." |
| `excel_valido.xlsx` | Archivo correcto | Carga exitosa |

> ⚠️ **`excel_valido.xlsx`**: al ser válido, la carga **persiste registros reales en
> Oracle**. Úsalo solo en local o un ambiente desechable, NO contra migr compartido.
> Los casos de error son seguros en cualquier ambiente (se rechazan antes de persistir).

Para generar la plantilla base, usa el botón "Descargar plantilla" de la pantalla
(`/finanzas/accounting-system/download-template/`) y modifícala según cada escenario.
