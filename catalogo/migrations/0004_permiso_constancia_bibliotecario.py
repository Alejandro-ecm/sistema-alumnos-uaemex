from django.apps import apps as django_apps
from django.db import migrations

CODENAMES = ('view_constanciadonacion', 'add_constanciadonacion', 'change_constanciadonacion')


def otorgar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # Mismo motivo que en auditoria/migrations/0002_permiso_auditoria_administrativos:
    # en una base de datos nueva los permisos de ConstanciaDonacion todavía no
    # existen en este punto de la corrida de `migrate` (se crean en la señal
    # post_migrate, al final).
    from django.contrib.auth.management import create_permissions
    for app_config in django_apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    grupo, _ = Group.objects.get_or_create(name='Bibliotecario')
    # .add() y no .set(): 'Bibliotecario' ya tiene permisos de catalogo y
    # circulacion desde alumnos/migraciones/0014_crear_grupo_bibliotecario —
    # .set() los reemplazaría en vez de sumar estos.
    for codename in CODENAMES:
        permiso = Permission.objects.filter(content_type__app_label='catalogo', codename=codename).first()
        if permiso:
            grupo.permissions.add(permiso)


def revocar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    try:
        grupo = Group.objects.get(name='Bibliotecario')
    except Group.DoesNotExist:
        return
    permisos = Permission.objects.filter(content_type__app_label='catalogo', codename__in=CODENAMES)
    grupo.permissions.remove(*permisos)


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0003_constanciadonacion_constanciadonacionlibro'),
        ('alumnos', '0014_crear_grupo_bibliotecario'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(otorgar_permisos, revocar_permisos),
    ]
