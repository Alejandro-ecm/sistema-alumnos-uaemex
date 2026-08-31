from django.db import migrations


# El rol "Mantenimiento" se manejaba con permisos de grupo (ver 0016/0017),
# pero eso deja fuera secciones y controles que Django reserva a
# user.is_superuser (además de que Jazzmin arma el menú lateral distinto
# para un superusuario real). Para que este rol tenga de verdad "todas las
# funciones de superusuario", se renombra el grupo a "Superusuario" y se
# promueve a is_superuser=True a quien ya estuviera en él. De aquí en
# adelante, elegir este rol en el alta/edición de usuarios (alumnos/admin.py)
# hace lo mismo automáticamente.
def renombrar_y_promover(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')

    try:
        grupo = Group.objects.get(name='Mantenimiento')
    except Group.DoesNotExist:
        grupo, _ = Group.objects.get_or_create(name='Superusuario')
    else:
        grupo.name = 'Superusuario'
        grupo.save(update_fields=['name'])

    User.objects.filter(groups=grupo).update(is_superuser=True, is_staff=True)


def revertir(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')

    try:
        grupo = Group.objects.get(name='Superusuario')
    except Group.DoesNotExist:
        return

    User.objects.filter(groups=grupo).update(is_superuser=False)
    grupo.name = 'Mantenimiento'
    grupo.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [
        ('alumnos', '0018_acervo_digital_para_todos_los_roles'),
    ]

    operations = [
        migrations.RunPython(renombrar_y_promover, revertir),
    ]
