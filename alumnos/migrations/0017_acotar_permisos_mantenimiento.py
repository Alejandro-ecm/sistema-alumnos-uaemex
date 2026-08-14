from django.db import migrations


# Mismo conjunto que PERMISOS_MANTENIMIENTO_ORIGINALES en 0016: lo único que
# el rol Mantenimiento usa de verdad es su panel (Vista de seguridad, vía
# deteccion_libros.view/change_eventodeteccion) y la tarjeta "Usuarios" de
# ese panel (alta/edición/borrado de cuentas, vía auth.*_user). La 0016 le
# había dado TODOS los permisos del sistema por error, lo que hacía que el
# menú lateral de Jazzmin le mostrara también Alumnos, Auditoría, Catálogo
# y Circulación (Jazzmin muestra cada sección según los permisos del
# usuario). Esta migración corrige eso quitándole lo que no le corresponde.
PERMISOS_MANTENIMIENTO = [
    ('deteccion_libros', 'view_eventodeteccion'),
    ('deteccion_libros', 'change_eventodeteccion'),
    ('auth', 'view_user'),
    ('auth', 'add_user'),
    ('auth', 'change_user'),
    ('auth', 'delete_user'),
]


def acotar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    try:
        grupo = Group.objects.get(name='Mantenimiento')
    except Group.DoesNotExist:
        return

    ids = []
    for app_label, codename in PERMISOS_MANTENIMIENTO:
        try:
            ids.append(
                Permission.objects.get(content_type__app_label=app_label, codename=codename).id
            )
        except Permission.DoesNotExist:
            continue
    grupo.permissions.set(ids)


def revertir(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    try:
        grupo = Group.objects.get(name='Mantenimiento')
    except Group.DoesNotExist:
        return
    grupo.permissions.set(Permission.objects.all())


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0016_mantenimiento_todos_los_permisos'),
    ]

    operations = [
        migrations.RunPython(acotar_permisos, revertir),
    ]
