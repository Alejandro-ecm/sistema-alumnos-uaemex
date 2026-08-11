import csv

from django.contrib import admin
from django.http import HttpResponse


def accion_exportar_csv(nombre_archivo, encabezados, extractor, descripcion='Exportar seleccionados a CSV'):
    @admin.action(description=descripcion)
    def accion(modeladmin, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}.csv"'
        writer = csv.writer(response)
        writer.writerow(encabezados)
        for obj in queryset:
            writer.writerow(extractor(obj))
        return response
    # El admin registra la acción bajo func.__name__; sin esto todas las
    # acciones generadas por esta factory colisionarían bajo el nombre "accion".
    accion.__name__ = f'exportar_{nombre_archivo}_csv'
    return accion
