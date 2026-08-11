from django.apps import apps as django_apps
from django.db import migrations


def otorgar_permiso(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # Mismo motivo que en alumnos/migrations/0013_crear_grupos_roles: en una
    # base de datos nueva el permiso view_registroauditoria todavía no existe
    # en este punto de la corrida de `migrate` (se crea en la señal
    # post_migrate, al final).
    from django.contrib.auth.management import create_permissions
    for app_config in django_apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    grupo, _ = Group.objects.get_or_create(name='Administrativos')
    try:
        permiso = Permission.objects.get(content_type__app_label='auditoria', codename='view_registroauditoria')
    except Permission.DoesNotExist:
        return
    # .add() y no .set(): 'Administrativos' ya tiene view/change/delete_alumno
    # desde la migración 0013 — .set() reemplazaría esos permisos en vez de
    # sumar este.
    grupo.permissions.add(permiso)


def revocar_permiso(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    try:
        grupo = Group.objects.get(name='Administrativos')
        permiso = Permission.objects.get(content_type__app_label='auditoria', codename='view_registroauditoria')
    except (Group.DoesNotExist, Permission.DoesNotExist):
        return
    grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ('auditoria', '0001_initial'),
        ('alumnos', '0013_crear_grupos_roles'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(otorgar_permiso, revocar_permiso),
    ]
