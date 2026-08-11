# Sistema de alumnos

Sistema de gestión escolar en Django: registro de alumnos, biblioteca
(catálogo, préstamos, devoluciones) y detección por visión artificial de
posibles robos/daños a libros.

## Apps

| App                | Propósito                                                              |
|--------------------|-------------------------------------------------------------------------|
| `auditoria`        | Bitácora de auditoría genérica (quién creó/modificó/eliminó qué y cuándo). |
| `alumnos`          | Alta de alumnos, generación de constancias PDF/DOCX, panel de administración por rol. |
| `catalogo`         | Registros bibliográficos, autores/editoriales/materias, ejemplares, exportación MARC XML, constancias de donación de libros (Word). |
| `circulacion`      | Préstamos y devoluciones de ejemplares, con integridad transaccional (`select_for_update`) y cobro de multas por atraso. |
| `deteccion_libros` | Eventos de detección (cámaras + YOLO): posible sustracción o ruptura de libros. |

## Roles y permisos

Los grupos se crean vía migraciones de datos (no manualmente en el admin),
para que cualquier base de datos nueva quede lista tras `migrate`:

- **Administrativos** (`alumnos/migrations/0013_crear_grupos_roles.py`,
  ampliado en `auditoria/migrations/0002_permiso_auditoria_administrativos.py`):
  gestión de alumnos (ver/editar/eliminar) y lectura de la bitácora de
  auditoría.
- **Mantenimiento** (`alumnos/migrations/0013_crear_grupos_roles.py`):
  gestión de eventos de detección y de usuarios del sistema.
- **Bibliotecario** (`alumnos/migrations/0014_crear_grupo_bibliotecario.py`,
  ampliado en `catalogo/migrations/0004_permiso_constancia_bibliotecario.py`
  y `catalogo/migrations/0005_permiso_constancialibro_bibliotecario.py`):
  gestión de catálogo (registros, ejemplares, autores, editoriales,
  materias), de préstamos/devoluciones con cobro de multas, y de
  constancias de donación de libros. Su panel (`panel_biblioteca`) muestra
  además los libros agregados recientemente y el resumen de constancias y
  multas.

El aterrizaje tras iniciar sesión en `/admin/` depende del grupo del
usuario (ver `alumnos/views.py`, sección "ATERRIZAJE EN /admin/ SEGÚN ROL").

## Cómo correr el proyecto (Windows, desarrollo local)

Todos los comandos de `manage.py` requieren `DEBUG=True` explícito — sin
esa variable, `settings.py` arranca en modo seguro (`DEBUG=False`) y
espera un `SECRET_KEY` de producción:

```
DEBUG=True venv/Scripts/python.exe manage.py migrate
DEBUG=True venv/Scripts/python.exe manage.py test
DEBUG=True venv/Scripts/python.exe manage.py runserver
```

## Constancias de donación y multas por atraso

- **Constancias de donación** (`catalogo.ConstanciaDonacion` /
  `ConstanciaDonacionLibro`): el bibliotecario da de alta la constancia
  (nombre del donante, cargo, fecha) en `/admin/catalogo/constanciadonacion/`,
  agrega los títulos donados y su cantidad mediante el inline, y usa la
  acción "Descargar constancia (Word)" para generar el `.docx` (folio
  `CONST-000001`, tabla de libros, firma institucional) con
  `catalogo/constancia_donacion.py`.
- **Multas por atraso** (`circulacion.Prestamo`): la tarifa
  (`TARIFA_MULTA_DIA`, actualmente $20 MXN/día) se calcula sobre los días
  vencidos al momento de la devolución. En vez de la acción masiva
  "Marcar como devuelto", cada préstamo activo muestra un enlace
  "Registrar devolución" que lleva a una página dedicada
  (`/admin/circulacion/prestamo/<id>/devolver/`) donde se ve la multa
  estimada y se captura el descuento aplicado, el monto cobrado y si ya
  fue pagada.

## Bitácora de auditoría

La app `auditoria` registra automáticamente cada creación, modificación y
eliminación de los modelos sensibles del sistema: `Alumno`,
`ImpresionConstancia`, `RegistroBibliografico`, `Ejemplar`,
`EventoDeteccion` y `Prestamo`.

- Para la mayoría de los modelos, el registro es automático vía señales
  `post_save`/`post_delete` (ver `<app>/signals.py` en `alumnos`,
  `catalogo` y `deteccion_libros`, conectadas desde `AppConfig.ready()`).
- **`circulacion.Prestamo` es un caso especial**: sus métodos
  `marcar_devuelto()` y `marcar_perdido()` usan
  `Prestamo.objects.filter(pk=...).update(...)` en vez de `.save()`, para
  mantener el lock de `select_for_update()` durante toda la transacción.
  Como `.update()` nunca dispara `post_save`, estos dos métodos (y la rama
  de creación de `save()`) llaman explícitamente a
  `auditoria.services.registrar()` en vez de depender de una señal
  genérica.
- El usuario autor del cambio se obtiene de una variable thread-local que
  llena `auditoria.middleware.UsuarioActualMiddleware` en cada request.
  Fuera del ciclo de una petición HTTP (shell, comandos de gestión,
  migraciones de datos), el registro queda con `usuario=None`.
- La bitácora se consulta en `/admin/auditoria/registroauditoria/`
  (solo lectura: sin alta, edición ni borrado desde el admin). Requiere el
  permiso `auditoria.view_registroauditoria`, que el grupo
  `Administrativos` ya tiene.
- No hay backfill retroactivo: el registro empieza a llenarse a partir de
  la migración de esta etapa, no reconstruye el historial previo.
