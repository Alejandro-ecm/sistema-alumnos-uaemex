from django.apps import apps as django_apps
from django.db import migrations

CODENAMES = ('view_constanciadonacionlibro', 'add_constanciadonacionlibro', 'change_constanciadonacionlibro')


def otorgar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    # Sin estos permisos el inline de ConstanciaDonacionLibro queda oculto
    # para Bibliotecario (Django admin exige permisos sobre el modelo del
    # inline, no solo sobre el modelo padre), y la constancia se guarda
    # sin ningún libro.
    from django.contrib.auth.management import create_permissions
    for app_config in django_apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    grupo, _ = Group.objects.get_or_create(name='Bibliotecario')
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
        ('catalogo', '0004_permiso_constancia_bibliotecario'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(otorgar_permisos, revocar_permisos),
    ]
