# Informe de robustez

## Resumen de cambios

- Se agregó protección concurrente contra participantes duplicados mediante un índice `UNIQUE` sobre nombre y apellido, respetando la regla preexistente.
- Antes de crear índices únicos se comprueba si existen datos duplicados. Si los hay, se informan y no se modifican ni eliminan registros.
- Las altas duplicadas capturan `IntegrityError`, ejecutan rollback y devuelven una respuesta controlada.
- Las operaciones críticas de alta, configuración, eliminación, reset e importación usan un solo commit y rollback explícito ante errores.
- SQLite usa `timeout=10` y `PRAGMA busy_timeout=10000` en cada conexión.
- Los bloqueos SQLite agotados devuelven HTTP 503, ejecutan rollback y quedan registrados sin datos sensibles.
- No se reejecutan transacciones completas; la espera por bloqueos ocurre internamente en SQLite y está acotada.
- Las exportaciones se generan en buffers `BytesIO` independientes, sin archivos compartidos ni residuos temporales.
- Se agregó logging limitado a errores importantes, rollbacks, bloqueos SQLite, cantidades importadas/eliminadas, errores de exportación y operaciones administrativas.
- Los logs no incluyen contraseñas, sesiones, cookies ni DNI completos.
- Los workbooks importados y creados se cierran explícitamente cuando corresponde.

## Archivos modificados

- `app.py`
- `INFORME_ROBUSTEZ.md`

## Funciones modificadas o agregadas

- `configurar_conexion_sqlite()`
- `es_bloqueo_sqlite()`
- `registrar_error_transaccion()`
- `rollback_transaccion()`
- `manejar_error_operacional()`
- `migrar_columna()`
- `crear_indices_unicos_si_es_posible()`
- Inicialización transaccional de base y configuración.
- `agregar()`
- `update_config()`
- `delete()`
- `reset()`
- `export()`
- `crear_exportacion_participantes()`
- `export_historial()`
- `crear_exportacion_historial()`
- `enviar_workbook()`
- `upload_hdcp()`
- `upload_bg()`

## Pruebas realizadas

- Parseo sintáctico completo de `app.py`: correcto.
- Render de `/` mediante cliente Flask: HTTP 200.
- Acceso a `/admin-secret`: HTTP 200.
- Login administrativo: redirección HTTP 302.
- Dos altas concurrentes idénticas: un único participante y un único movimiento persistidos.
- Verificación del índice `uq_participante_nombre_apellido`.
- Base heredada con duplicados: datos preservados, índice no creado y nuevas altas bloqueadas con HTTP 503.
- Fallo forzado durante reset: rollback integral, participantes preservados y ningún movimiento parcial.
- Reset normal: participantes eliminados y movimientos/resumen confirmados en una transacción.
- Actualización administrativa de configuración: HTTP 302.
- Eliminación administrativa: HTTP 200.
- Importación de `Libro1.xlsx`: 68 registros importados.
- Importación inválida: HTTP 400, rollback y 68 registros anteriores preservados.
- Dos exportaciones simultáneas: HTTP 200 para ambas, nombres correctos y buffers independientes.
- Verificación de hojas y encabezados de ambas exportaciones.
- Verificación de ausencia de `participantes.xlsx` e `historial_movimientos.xlsx` residuales.
- Error de exportación forzado: HTTP 500 controlado y evento registrado.
- Bloqueo SQLite real: espera acotada, rollback, log y HTTP 503; sin inserción parcial.
- Comprobación del valor efectivo `PRAGMA busy_timeout`: 10000 ms.
- Revisión de logs generados: sin contraseñas, sesiones, cookies ni los DNI utilizados en las pruebas.
- Arranque de servidor Flask-SocketIO real en copia temporal: inicio correcto y respuesta HTTP 200.
- `pip check`: no se detectaron dependencias instaladas rotas.

## Riesgos encontrados

- En esta PC existe `C:\var\data`. La condición `os.path.exists("/var/data")` selecciona esa ruta también en Windows. Las pruebas se ejecutaron en copias aisladas para no tocar datos potencialmente reales.
- La URI SQLite relativa de Flask-SQLAlchemy puede resolverse respecto de `instance_path`, mientras `os.makedirs(BASE_PATH)` crea el directorio respecto del proceso. No se corrigió porque excede el alcance autorizado y podría cambiar la ubicación efectiva de datos.
- Si una base heredada ya contiene participantes duplicados, las altas quedan bloqueadas hasta una revisión manual. No se elimina ni corrige información automáticamente.
- El repositorio no tiene commits; todos los archivos aparecen sin seguimiento. Por eso `git diff --stat` no muestra los cambios de archivos untracked.
- El entorno virtual completo está dentro del directorio del proyecto y también permanece sin seguimiento. No se modificó por estar fuera del alcance.
- No existe una suite de tests permanente en el proyecto. Las verificaciones se ejecutaron contra copias temporales aisladas.

## git diff --stat

`git diff --stat` no produjo salida porque el repositorio no tiene commits y los archivos están sin seguimiento.

## git status

```text
## No commits yet on master
?? INFORME_ROBUSTEZ.md
?? Include/
?? Lib/
?? Libro1.xlsx
?? Procfile
?? Scripts/
?? app.py
?? datos.db
?? pyvenv.cfg
?? requirements.txt
?? templates/
```

No se realizó commit, push, pull, fetch, merge ni ninguna operación remota.
