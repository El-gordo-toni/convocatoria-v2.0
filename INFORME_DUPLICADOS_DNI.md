# Informe de duplicados de DNI o matrícula

## Alcance

Inspección de solo lectura de la base efectiva detectada localmente en `C:\var\data\datos.db`.

La comparación se realizó con el mismo criterio implementado en la aplicación: para documentos numéricos se eliminan espacios, puntos y guiones antes de comparar.

No se eliminó, combinó ni modificó ningún participante existente.

## Resultado

- Participantes inspeccionados: **22**.
- Grupos con nombres normalizados duplicados: **0**.
- Grupos con DNI o matrícula normalizados duplicados: **2**.

### Grupo 1

- IDs afectados: `1`, `18`, `19`, `20`.
- Valor normalizado enmascarado: `**3456`.
- Cantidad de registros: `4`.

### Grupo 2

- IDs afectados: `2`, `4`.
- Valor normalizado enmascarado: `****5689`.
- Cantidad de registros: `2`.

## Corrección manual requerida

Se debe revisar cada ID en la base efectiva y determinar cuál es el DNI correcto de cada persona. No corresponde decidir automáticamente qué registro conservar, borrar o modificar.

Mientras existan estos grupos:

- La aplicación no creará el índice único de DNI normalizado.
- La aplicación sí podrá iniciar.
- Las validaciones y triggers impedirán crear nuevas repeticiones.
- Las altas con DNI nuevos continuarán funcionando.

Después de corregir manualmente los valores duplicados, el próximo inicio podrá crear el índice único de forma automática y repetible.
