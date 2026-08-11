from django.apps import apps as django_apps
from django.db import migrations


PERMISOS_ADMINISTRATIVOS = [
    ('alumnos', 'view_alumno'),
    ('alumnos', 'change_alumno'),
    ('alumnos', 'delete_alumno'),
]

PERMISOS_MANTENIMIENTO = [
    ('deteccion_libros', 'view_eventodeteccion'),
    ('deteccion_libros', 'change_eventodeteccion'),
    ('auth', 'view_user'),
    ('auth', 'add_user'),
    ('auth', 'change_user'),
    ('auth', 'delete_user'),
]


def crear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # En una base de datos NUEVA (todas las migraciones en una sola corrida de
    # `migrate`), los permisos de cada modelo (view_alumno, view_eventodeteccion,
    # etc.) todavía no existen en este punto: Django los crea vía la señal
    # post_migrate, que se emite una sola vez al final, después de esta
    # migración de datos. Sin esto, Permission.objects.get(...) fallaría
    # silenciosamente (except Permission.DoesNotExist: continue) y los grupos
    # quedarían creados sin ningún permiso. Mismo patrón que usa Django para
    # su propia migración auth.0011_update_proxy_permissions.
    from django.contrib.auth.management import create_permissions
    for app_config in django_apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    def asignar(nombre_grupo, permisos):
        grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
        ids = []
        for app_label, codename in permisos:
            try:
                ids.append(
                    Permission.objects.get(content_type__app_label=app_label, codename=codename).id
                )
            except Permission.DoesNotExist:
                continue
        grupo.permissions.set(ids)

    asignar('Administrativos', PERMISOS_ADMINISTRATIVOS)
    asignar('Mantenimiento', PERMISOS_MANTENIMIENTO)


def borrar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['Administrativos', 'Mantenimiento']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0012_impresionconstancia'),
        ('deteccion_libros', '0001_initial'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, borrar_grupos),
    ]
