from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from proyecto.admin_utils import accion_exportar_csv

from .models import Prestamo


exportar_prestamos_csv = accion_exportar_csv(
    'prestamos',
    ['Código de barras', 'Título', 'Alumno (cuenta)', 'Alumno (nombre)', 'Fecha préstamo',
     'Fecha vencimiento', 'Fecha devolución', 'Estado', 'Vencido'],
    lambda p: [
        p.ejemplar.codigo_barras, p.ejemplar.registro.titulo,
        p.alumno.numero_cuenta if p.alumno else '', p.alumno.nombre if p.alumno else '',
        p.fecha_prestamo, p.fecha_vencimiento, p.fecha_devolucion or '',
        p.get_estado_display(), 'Sí' if p.vencido else 'No',
    ],
)


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ('ejemplar', 'alumno', 'fecha_prestamo', 'fecha_vencimiento', 'estado', 'vencido')
    list_filter = ('estado',)
    search_fields = ('ejemplar__codigo_barras', 'ejemplar__registro__titulo', 'alumno__nombre')
    autocomplete_fields = ['ejemplar']
    raw_id_fields = ['alumno']
    actions = ['marcar_devuelto', 'marcar_perdido', exportar_prestamos_csv]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.readonly_fields
        return (*self.readonly_fields, 'ejemplar', 'estado', 'fecha_devolucion', 'fecha_prestamo')

    @admin.display(boolean=True, description='Vencido')
    def vencido(self, obj):
        return obj.vencido

    @admin.action(description='Marcar como devuelto')
    def marcar_devuelto(self, request, queryset):
        actualizados = 0
        for prestamo in queryset:
            try:
                prestamo.marcar_devuelto()
                actualizados += 1
            except ValidationError as e:
                self.message_user(request, f'{prestamo}: {e.message}', level=messages.WARNING)
        if actualizados:
            self.message_user(request, f'{actualizados} préstamo(s) marcado(s) como devuelto.')

    @admin.action(description='Marcar como perdido')
    def marcar_perdido(self, request, queryset):
        actualizados = 0
        for prestamo in queryset:
            try:
                prestamo.marcar_perdido()
                actualizados += 1
            except ValidationError as e:
                self.message_user(request, f'{prestamo}: {e.message}', level=messages.WARNING)
        if actualizados:
            self.message_user(request, f'{actualizados} préstamo(s) marcado(s) como perdido.')
