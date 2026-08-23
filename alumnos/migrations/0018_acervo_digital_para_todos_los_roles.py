from django.apps import apps as django_apps
from django.db import migrations


# El link "Acervo Digital" del menú (JAZZMIN_SETTINGS.custom_links) y el
# panel que lo sirve (catalogo.admin.panel_biblioteca) están protegidos con
# catalogo.view_registrobibliografico. Hasta ahora solo el grupo
# Bibliotecario tenía ese permiso, así que Administrativos y Mantenimiento
# no veían el link ni podían abrir la URL directamente (PermissionDenied).
# Se agrega (no se reemplaza) ese permiso a ambos grupos para que el Acervo
# Digital quede disponible desde los 3 roles de acceso.
GRUPOS_DESTINO = ['Administrativos', 'Mantenimiento']
PERMISO = ('catalogo', 'view_registrobibliografico')


def dar_permiso(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    from django.contrib.auth.management import create_permissions
    for app_config in django_apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    try:
        permiso = Permission.objects.get(content_type__app_label=PERMISO[0], codename=PERMISO[1])
    except Permission.DoesNotExist:
        return

    for nombre_grupo in GRUPOS_DESTINO:
        try:
            grupo = Group.objects.get(name=nombre_grupo)
        except Group.DoesNotExist:
            continue
        grupo.permissions.add(permiso)


def quitar_permiso(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    try:
        permiso = Permission.objects.get(content_type__app_label=PERMISO[0], codename=PERMISO[1])
    except Permission.DoesNotExist:
        return

    for nombre_grupo in GRUPOS_DESTINO:
        try:
            grupo = Group.objects.get(name=nombre_grupo)
        except Group.DoesNotExist:
            continue
        grupo.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0017_acotar_permisos_mantenimiento'),
        ('catalogo', '0006_registrobibliografico_alumno'),
    ]

    operations = [
        migrations.RunPython(dar_permiso, quitar_permiso),
    ]
