from django.db import migrations


def borrar_prestamos_y_liberar_ejemplares(apps, schema_editor):
    """El formato de préstamo cambia de 'un libro por préstamo' a 'varios
    libros por folio', así que no hay una conversión 1:1 razonable del
    historial existente. Se arranca en blanco (decisión confirmada con el
    usuario) y se liberan los ejemplares que estaban marcados como
    prestados por préstamos activos, para que no queden bloqueados."""
    Prestamo = apps.get_model('circulacion', 'Prestamo')
    Ejemplar = apps.get_model('catalogo', 'Ejemplar')

    ejemplar_ids = list(
        Prestamo.objects.filter(estado='ACTIVO').values_list('ejemplar_id', flat=True)
    )
    Ejemplar.objects.filter(pk__in=ejemplar_ids, estado='PRESTADO').update(estado='DISPONIBLE')
    Prestamo.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('circulacion', '0003_prestamo_dias_retraso_prestamo_multa_cobrada_and_more'),
        ('catalogo', '0006_registrobibliografico_alumno'),
    ]

    operations = [
        migrations.RunPython(borrar_prestamos_y_liberar_ejemplares, migrations.RunPython.noop),
    ]
