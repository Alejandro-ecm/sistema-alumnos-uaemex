import datetime

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from catalogo.models import Ejemplar

from .forms import DevolucionForm, PrestamoForm
from .models import PLAZO_PRESTAMO_DIAS, TARIFA_MULTA_DIA, Prestamo
from .recibo import generar_recibo_docx
from .services import crear_prestamo


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    """Todo el flujo de préstamos vive en vistas propias (lista con
    modal de alta, detalle, devolución, recibo) en vez del changelist
    estándar de Django admin, para poder mostrar el formato de tarjetas
    / tabla que pidió el bibliotecario. Los nombres de las URLs de admin
    (circulacion_prestamo_changelist, etc.) se conservan para que los
    enlaces que ya existen en catalogo/panel_biblioteca.html sigan
    funcionando."""

    def has_module_permission(self, request):
        return request.user.has_perm('circulacion.view_prestamo')

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('buscar-libros/', self.admin_site.admin_view(self.buscar_libros),
                 name='circulacion_prestamo_buscar_libros'),
            path('crear/', self.admin_site.admin_view(self.crear),
                 name='circulacion_prestamo_crear'),
            path('<int:pk>/', self.admin_site.admin_view(self.detalle),
                 name='circulacion_prestamo_detalle'),
            path('<int:pk>/devolver/', self.admin_site.admin_view(self.registrar_devolucion),
                 name='circulacion_prestamo_devolver'),
            path('<int:pk>/perdido/', self.admin_site.admin_view(self.marcar_perdido_vista),
                 name='circulacion_prestamo_perdido'),
            path('<int:pk>/recibo/', self.admin_site.admin_view(self.descargar_recibo),
                 name='circulacion_prestamo_recibo'),
        ]
        return extra + urls

    def changelist_view(self, request, extra_context=None):
        if not request.user.has_perm('circulacion.view_prestamo'):
            raise PermissionDenied

        buscar = request.GET.get('q', '').strip()
        estado = request.GET.get('estado', '').strip()

        prestamos = Prestamo.objects.prefetch_related('libros__ejemplar__registro').order_by('-fecha_prestamo')
        if buscar:
            prestamos = prestamos.filter(
                Q(folio__icontains=buscar) | Q(alumno_nombre__icontains=buscar) | Q(matricula__icontains=buscar)
            )
        if estado:
            prestamos = prestamos.filter(estado=estado)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Préstamos',
            'prestamos': prestamos,
            'total_prestamos': Prestamo.objects.count(),
            'buscar': buscar,
            'estado_filtro': estado,
            'estados': Prestamo.ESTADOS,
            'hoy': timezone.localdate(),
            'form': PrestamoForm(initial={
                'fecha_salida': timezone.localdate(),
                'fecha_devolucion': timezone.localdate() + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS),
            }),
        }
        return TemplateResponse(request, 'circulacion/prestamos_lista.html', context)

    def buscar_libros(self, request):
        if not request.user.has_perm('circulacion.add_prestamo'):
            raise PermissionDenied
        q = request.GET.get('q', '').strip()
        ejemplares = Ejemplar.objects.filter(estado='DISPONIBLE').select_related('registro')
        if q:
            ejemplares = ejemplares.filter(Q(registro__titulo__icontains=q) | Q(codigo_barras__icontains=q))
        resultados = [
            {'id': e.pk, 'titulo': e.registro.titulo, 'codigo_barras': e.codigo_barras}
            for e in ejemplares.order_by('registro__titulo')[:15]
        ]
        return JsonResponse({'resultados': resultados})

    def crear(self, request):
        if not request.user.has_perm('circulacion.add_prestamo'):
            raise PermissionDenied
        if request.method != 'POST':
            return redirect('admin:circulacion_prestamo_changelist')

        form = PrestamoForm(request.POST)
        if form.is_valid():
            try:
                prestamo = crear_prestamo(
                    alumno_nombre=form.cleaned_data['alumno_nombre'],
                    matricula=form.cleaned_data['matricula'],
                    telefono=form.cleaned_data['telefono'],
                    carrera=form.cleaned_data['carrera'],
                    fecha_salida=form.cleaned_data['fecha_salida'],
                    fecha_devolucion=form.cleaned_data['fecha_devolucion'],
                    observaciones=form.cleaned_data['observaciones'],
                    ejemplar_ids=form.cleaned_data['ejemplares'],
                )
                self.message_user(
                    request,
                    f'Préstamo {prestamo.folio} registrado. Descarga el recibo desde la lista.',
                )
            except ValidationError as e:
                mensaje = e.message if hasattr(e, 'message') else '; '.join(e.messages)
                self.message_user(request, mensaje, level=messages.ERROR)
        else:
            errores = '; '.join(f'{campo}: {", ".join(m)}' for campo, m in form.errors.items())
            self.message_user(request, f'Revisa los datos del préstamo: {errores}', level=messages.ERROR)

        return redirect('admin:circulacion_prestamo_changelist')

    def detalle(self, request, pk):
        if not request.user.has_perm('circulacion.view_prestamo'):
            raise PermissionDenied
        prestamo = get_object_or_404(
            Prestamo.objects.prefetch_related('libros__ejemplar__registro'), pk=pk
        )
        context = {
            **self.admin_site.each_context(request),
            'title': f'Préstamo {prestamo.folio}',
            'prestamo': prestamo,
        }
        return TemplateResponse(request, 'circulacion/prestamo_detalle.html', context)

    def registrar_devolucion(self, request, pk):
        prestamo = get_object_or_404(Prestamo, pk=pk)
        if not request.user.has_perm('circulacion.change_prestamo'):
            raise PermissionDenied
        if prestamo.estado != 'ACTIVO':
            self.message_user(request, 'Este préstamo ya no está activo.', level=messages.WARNING)
            return redirect('admin:circulacion_prestamo_detalle', pk)

        dias_retraso = max(0, (timezone.localdate() - prestamo.fecha_devolucion).days)
        multa_estimada = dias_retraso * TARIFA_MULTA_DIA

        if request.method == 'POST':
            form = DevolucionForm(request.POST)
            if form.is_valid():
                try:
                    prestamo.marcar_devuelto(**form.cleaned_data)
                    self.message_user(request, f'Devolución registrada para {prestamo.folio}.')
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

    def marcar_perdido_vista(self, request, pk):
        prestamo = get_object_or_404(Prestamo, pk=pk)
        if not request.user.has_perm('circulacion.change_prestamo'):
            raise PermissionDenied
        if request.method == 'POST':
            try:
                prestamo.marcar_perdido()
                self.message_user(request, f'Préstamo {prestamo.folio} marcado como perdido.')
            except ValidationError as e:
                self.message_user(request, e.message, level=messages.ERROR)
        return redirect('admin:circulacion_prestamo_changelist')

    def descargar_recibo(self, request, pk):
        if not request.user.has_perm('circulacion.view_prestamo'):
            raise PermissionDenied
        prestamo = get_object_or_404(
            Prestamo.objects.prefetch_related('libros__ejemplar__registro'), pk=pk
        )
        doc = generar_recibo_docx(prestamo)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{prestamo.folio}.docx"'
        doc.save(response)
        return response
