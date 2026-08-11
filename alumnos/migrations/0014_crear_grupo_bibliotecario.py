from django.apps import apps as django_apps
from django.db import migrations


PERMISOS_BIBLIOTECARIO = [
    ('catalogo', 'view_registrobibliografico'),
    ('catalogo', 'add_registrobibliografico'),
    ('catalogo', 'change_registrobibliografico'),
    ('catalogo', 'view_ejemplar'),
    ('catalogo', 'add_ejemplar'),
    ('catalogo', 'change_ejemplar'),
    ('catalogo', 'view_autor'),
    ('catalogo', 'add_autor'),
    ('catalogo', 'change_autor'),
    ('catalogo', 'view_editorial'),
    ('catalogo', 'add_editorial'),
    ('catalogo', 'change_editorial'),
    ('catalogo', 'view_materia'),
    ('catalogo', 'add_materia'),
    ('catalogo', 'change_materia'),
    ('circulacion', 'view_prestamo'),
    ('circulacion', 'add_prestamo'),
    ('circulacion', 'change_prestamo'),
]


def crear_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # Mismo motivo que en 0013_crear_grupos_roles: en una base de datos
    # nueva los permisos de catalogo/circulacion todavía no existen en
    # este punto de la corrida de `migrate` (se crean en la señal
    # post_migrate, al final).
    from django.contrib.auth.management import create_permissions
    for app_config in django_apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    grupo, _ = Group.objects.get_or_create(name='Bibliotecario')
    ids = []
    for app_label, codename in PERMISOS_BIBLIOTECARIO:
        try:
            ids.append(
                Permission.objects.get(content_type__app_label=app_label, codename=codename).id
            )
        except Permission.DoesNotExist:
            continue
    grupo.permissions.set(ids)


def borrar_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Bibliotecario').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0013_crear_grupos_roles'),
        ('catalogo', '0002_alter_autor_nombre'),
        ('circulacion', '0002_alter_prestamo_fecha_vencimiento'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_grupo, borrar_grupo),
    ]
