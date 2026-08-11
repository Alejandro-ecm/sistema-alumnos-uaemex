from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from proyecto.admin_utils import accion_exportar_csv

from .forms import DevolucionForm
from .models import TARIFA_MULTA_DIA, Prestamo


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
    list_display = (
        'ejemplar', 'alumno', 'fecha_prestamo', 'fecha_vencimiento', 'estado', 'vencido',
        'multa_total', 'multa_pagada', 'acciones',
    )
    list_filter = ('estado', 'multa_pagada')
    search_fields = ('ejemplar__codigo_barras', 'ejemplar__registro__titulo', 'alumno__nombre')
    autocomplete_fields = ['ejemplar']
    raw_id_fields = ['alumno']
    actions = ['marcar_perdido', exportar_prestamos_csv]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.readonly_fields
        return (*self.readonly_fields, 'ejemplar', 'estado', 'fecha_devolucion', 'fecha_prestamo')

    @admin.display(boolean=True, description='Vencido')
    def vencido(self, obj):
        return obj.vencido

    @admin.display(description='')
    def acciones(self, obj):
        if obj.estado != 'ACTIVO':
            return '—'
        url = reverse('admin:circulacion_prestamo_devolver', args=[obj.pk])
        return format_html('<a class="button" href="{}">Registrar devolución</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('<int:pk>/devolver/', self.admin_site.admin_view(self.registrar_devolucion),
                 name='circulacion_prestamo_devolver'),
        ]
        return extra + urls

    def registrar_devolucion(self, request, pk):
        prestamo = get_object_or_404(Prestamo, pk=pk)
        if not request.user.has_perm('circulacion.change_prestamo'):
            raise PermissionDenied
        if prestamo.estado != 'ACTIVO':
            self.message_user(request, 'Este préstamo ya no está activo.', level=messages.WARNING)
            return redirect('admin:circulacion_prestamo_changelist')

        dias_retraso = max(0, (timezone.now().date() - prestamo.fecha_vencimiento).days)
        multa_estimada = dias_retraso * TARIFA_MULTA_DIA

        if request.method == 'POST':
            form = DevolucionForm(request.POST)
            if form.is_valid():
                try:
                    prestamo.marcar_devuelto(**form.cleaned_data)
                    self.message_user(request, f'Devolución registrada para {prestamo}.')
                    return redirect('admin:circulacion_prestamo_changelist')
                except ValidationError as e:
                    self.message_user(request, e.message, level=messages.ERROR)
        else:
            form = DevolucionForm(initial={'multa_cobrada': multa_estimada})

        context = {
            **self.admin_site.each_context(request),
            'title': 'Registrar devolución',
            'prestamo': prestamo,
            'dias_retraso': dias_retraso,
            'multa_estimada': multa_estimada,
            'form': form,
        }
        return TemplateResponse(request, 'circulacion/registrar_devolucion.html', context)

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
