from django.apps import apps as django_apps
from django.db import migrations


PERMISOS_MANTENIMIENTO_ORIGINALES = [
    ('deteccion_libros', 'view_eventodeteccion'),
    ('deteccion_libros', 'change_eventodeteccion'),
    ('auth', 'view_user'),
    ('auth', 'add_user'),
    ('auth', 'change_user'),
    ('auth', 'delete_user'),
]


def dar_todos_los_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # Mismo motivo que en 0013_crear_grupos_roles: en una base de datos
    # nueva los permisos de cada app todavía no existen en este punto de la
    # corrida de `migrate` (se crean en la señal post_migrate, al final).
    from django.contrib.auth.management import create_permissions
    for app_config in django_apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    grupo, _ = Group.objects.get_or_create(name='Mantenimiento')
    grupo.permissions.set(Permission.objects.all())


def restaurar_permisos_originales(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    try:
        grupo = Group.objects.get(name='Mantenimiento')
    except Group.DoesNotExist:
        return

    ids = []
    for app_label, codename in PERMISOS_MANTENIMIENTO_ORIGINALES:
        try:
            ids.append(
                Permission.objects.get(content_type__app_label=app_label, codename=codename).id
            )
        except Permission.DoesNotExist:
            continue
    grupo.permissions.set(ids)


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0015_alumno_libro_autor_alumno_libro_edicion_and_more'),
        ('catalogo', '0005_permiso_constancialibro_bibliotecario'),
        ('circulacion', '0003_prestamo_dias_retraso_prestamo_multa_cobrada_and_more'),
        ('auditoria', '0002_permiso_auditoria_administrativos'),
        ('deteccion_libros', '0001_initial'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(dar_todos_los_permisos, restaurar_permisos_originales),
    ]
