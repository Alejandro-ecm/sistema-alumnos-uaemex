from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from proyecto.admin_utils import accion_exportar_csv

from .constancia_donacion import generar_constancia_donacion_docx
from .excel_inventario import exportar_inventario_xlsx, generar_plantilla_xlsx, importar_libros_xlsx
from .forms import ImportarLibrosForm, ImportarMarcForm
from .marc import generar_marc_binario, generar_marc_xml
from .models import (
    Autor, AutorRegistro, ConstanciaDonacion, ConstanciaDonacionLibro,
    Editorial, Ejemplar, Materia, RegistroBibliografico,
)
from .services import exportar_marc_coleccion, importar_marc


def _respuesta_xlsx(workbook, nombre_archivo):
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    workbook.save(response)
    return response


class AutorRegistroInline(admin.TabularInline):
    model = AutorRegistro
    extra = 1
    autocomplete_fields = ['autor']


class EjemplarInline(admin.TabularInline):
    model = Ejemplar
    extra = 1
    fields = ('codigo_barras', 'ubicacion', 'estado', 'fecha_adquisicion')


@admin.register(RegistroBibliografico)
class RegistroBibliograficoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'editorial', 'anio_publicacion', 'clasificacion', 'isbn')
    list_filter = ('editorial', 'materias', 'idioma')
    search_fields = ('titulo', 'subtitulo', 'isbn', 'clasificacion', 'autores__nombre', 'editorial__nombre')
    filter_horizontal = ('materias',)
    inlines = [AutorRegistroInline, EjemplarInline]
    readonly_fields = ('marc_xml_preview',)
    actions = ['generar_marc21']
    fieldsets = (
        ('Datos generales', {'fields': ('titulo', 'subtitulo', 'isbn', 'edicion', 'anio_publicacion', 'idioma')}),
        ('Publicación', {'fields': ('editorial', 'lugar_publicacion')}),
        ('Clasificación y descripción', {'fields': ('clasificacion', 'descripcion_fisica', 'materias', 'notas')}),
        ('MARC21', {'classes': ('collapse',), 'fields': ('marc_xml_preview',)}),
    )

    @admin.display(description='MARC21 (XML)')
    def marc_xml_preview(self, obj):
        if not obj.marc_xml:
            return 'Aún no generado. Selecciona el registro en el listado y usa la acción "Generar/actualizar MARC21".'
        return format_html(
            '<pre style="max-height:420px;overflow:auto;white-space:pre-wrap;'
            'font-family:monospace;font-size:12px;background:#f5f5f5;padding:10px;'
            'border-radius:6px;">{}</pre>',
            obj.marc_xml,
        )

    @admin.action(description='Generar/actualizar MARC21')
    def generar_marc21(self, request, queryset):
        actualizados = 0
        for registro in queryset:
            registro.marc_xml = generar_marc_xml(registro)
            registro.save(update_fields=['marc_xml'])
            actualizados += 1
        self.message_user(request, f'MARC21 generado para {actualizados} registro(s).')

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('marc21/', self.admin_site.admin_view(self.tabla_marc21),
                 name='catalogo_marc21'),
            path('marc21/generar-todos/', self.admin_site.admin_view(self.marc21_generar_todos),
                 name='catalogo_marc21_generar_todos'),
            path('marc21/<int:registro_id>/descargar/<str:formato>/',
                 self.admin_site.admin_view(self.marc21_descargar), name='catalogo_marc21_descargar'),
            path('marc21/exportar-todos/<str:formato>/',
                 self.admin_site.admin_view(self.marc21_exportar_todos), name='catalogo_marc21_exportar_todos'),
            path('marc21/importar/', self.admin_site.admin_view(self.marc21_importar),
                 name='catalogo_marc21_importar'),
            path('panel-biblioteca/', self.admin_site.admin_view(self.panel_biblioteca),
                 name='catalogo_panel_biblioteca'),
            path('panel-biblioteca/importar/', self.admin_site.admin_view(self.panel_biblioteca_importar),
                 name='catalogo_panel_biblioteca_importar'),
            path('panel-biblioteca/plantilla/', self.admin_site.admin_view(self.panel_biblioteca_plantilla),
                 name='catalogo_panel_biblioteca_plantilla'),
            path('panel-biblioteca/exportar/', self.admin_site.admin_view(self.panel_biblioteca_exportar),
                 name='catalogo_panel_biblioteca_exportar'),
            path('panel-biblioteca/imprimir/', self.admin_site.admin_view(self.panel_biblioteca_imprimir),
                 name='catalogo_panel_biblioteca_imprimir'),
        ]
        return extra + urls

    def tabla_marc21(self, request):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        registros = RegistroBibliografico.objects.select_related('editorial', 'alumno').prefetch_related(
            'autorregistro_set__autor'
        ).order_by('-fecha_alta')
        context = {
            **self.admin_site.each_context(request),
            'title': 'MARC21',
            'registros': registros,
        }
        return TemplateResponse(request, 'catalogo/marc21.html', context)

    def marc21_generar_todos(self, request):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        actualizados = 0
        for registro in RegistroBibliografico.objects.all():
            registro.marc_xml = generar_marc_xml(registro)
            registro.save(update_fields=['marc_xml'])
            actualizados += 1
        self.message_user(request, f'MARC21 generado para {actualizados} registro(s).')
        return redirect('admin:catalogo_marc21')

    def marc21_descargar(self, request, registro_id, formato):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        if formato not in ('xml', 'mrc'):
            raise Http404
        registro = get_object_or_404(RegistroBibliografico, pk=registro_id)
        nombre_archivo = f'UAEMEX{registro.id:08d}.{formato}'
        if formato == 'mrc':
            response = HttpResponse(generar_marc_binario(registro), content_type='application/marc')
        else:
            response = HttpResponse(generar_marc_xml(registro), content_type='application/marcxml+xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        return response

    def marc21_exportar_todos(self, request, formato):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        if formato not in ('xml', 'mrc'):
            raise Http404
        contenido = exportar_marc_coleccion(formato)
        content_type = 'application/marc' if formato == 'mrc' else 'application/marcxml+xml; charset=utf-8'
        response = HttpResponse(contenido, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="catalogo_uaemex.{formato}"'
        return response

    def marc21_importar(self, request):
        if not request.user.has_perm('catalogo.add_registrobibliografico'):
            raise PermissionDenied
        resultado = None
        if request.method == 'POST':
            form = ImportarMarcForm(request.POST, request.FILES)
            if form.is_valid():
                resultado = importar_marc(form.cleaned_data['archivo'])
                if resultado.get('error'):
                    self.message_user(request, resultado['error'], level=messages.ERROR)
                else:
                    self.message_user(
                        request,
                        f"Importación MARC21 lista: {resultado['nuevos']} nuevo(s), "
                        f"{resultado['actualizados']} actualizado(s)"
                        + (f", {resultado['errores']} error(es)" if resultado['errores'] else ''),
                    )
                form = ImportarMarcForm()
        else:
            form = ImportarMarcForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Importar registros MARC21',
            'form': form,
            'resultado': resultado,
        }
        return TemplateResponse(request, 'catalogo/importar_marc.html', context)

    def panel_biblioteca(self, request):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        # import local: catalogo no depende de circulacion a nivel de módulo
        from circulacion.services import multas_por_libro, multas_recientes, resumen_multas, resumen_prestamos
        from .services import actividad_mensual, top_libros
        resumen = resumen_prestamos()
        multas = resumen_multas()
        context = {
            **self.admin_site.each_context(request),
            'title': 'Panel Biblioteca',
            'total_ejemplares': Ejemplar.objects.count(),
            'ejemplares_disponibles': Ejemplar.objects.filter(estado='DISPONIBLE').count(),
            'prestamos_activos': resumen.activos,
            'prestamos_vencidos': resumen.vencidos,
            'resumen_prestamos': resumen,
            'libros_recientes': RegistroBibliografico.objects.order_by('-fecha_alta')[:5],
            'acervo_digital': RegistroBibliografico.objects.select_related('editorial', 'alumno')
                .prefetch_related('autorregistro_set__autor', 'materias')
                .order_by('-fecha_alta'),
            'constancias_recientes': ConstanciaDonacion.objects.select_related('generado_por')
                .prefetch_related('libros__registro')[:5],
            'constancias_total': ConstanciaDonacion.objects.count(),
            'multas': multas,
            'top_libros': top_libros(),
            'actividad': actividad_mensual(),
            'multas_por_libro': multas_por_libro(),
            'multas_recientes': multas_recientes(),
        }
        return TemplateResponse(request, 'catalogo/panel_biblioteca.html', context)

    def panel_biblioteca_importar(self, request):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        resultado = None
        if request.method == 'POST':
            form = ImportarLibrosForm(request.POST, request.FILES)
            if form.is_valid():
                resultado = importar_libros_xlsx(form.cleaned_data['archivo'])
                if resultado.get('error'):
                    self.message_user(request, resultado['error'], level=messages.ERROR)
                else:
                    self.message_user(
                        request,
                        f"Importación lista: {resultado['nuevos']} nuevo(s), "
                        f"{resultado['actualizados']} actualizado(s)"
                        + (f", {resultado['errores']} error(es)" if resultado['errores'] else ''),
                    )
                form = ImportarLibrosForm()
        else:
            form = ImportarLibrosForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Importar libros desde Excel',
            'form': form,
            'resultado': resultado,
        }
        return TemplateResponse(request, 'catalogo/importar_libros.html', context)

    def panel_biblioteca_plantilla(self, request):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        return _respuesta_xlsx(generar_plantilla_xlsx(), 'plantilla_inventario.xlsx')

    def panel_biblioteca_exportar(self, request):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        tipo = request.GET.get('tipo', 'todos')
        fecha = timezone.now().strftime('%Y-%m-%d')
        nombres = {
            'este_mes': f'libros_este_mes_{fecha}.xlsx',
            'ultima_carga': f'ultima_carga_{fecha}.xlsx',
        }
        nombre_archivo = nombres.get(tipo, f'inventario_{fecha}.xlsx')
        return _respuesta_xlsx(exportar_inventario_xlsx(tipo), nombre_archivo)

    def panel_biblioteca_imprimir(self, request):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        registros = RegistroBibliografico.objects.select_related('editorial').prefetch_related('autores').annotate(
            total_ejemplares=Count('ejemplares', distinct=True),
            disponibles=Count('ejemplares', filter=Q(ejemplares__estado='DISPONIBLE'), distinct=True),
            prestados=Count('ejemplares', filter=Q(ejemplares__estado='PRESTADO'), distinct=True),
        ).order_by('titulo')
        context = {
            'title': 'Inventario de biblioteca',
            'registros': registros,
            'fecha_impresion': timezone.now(),
        }
        return TemplateResponse(request, 'catalogo/imprimir_inventario.html', context)


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


@admin.register(Editorial)
class EditorialAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


@admin.register(Materia)
class MateriaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


exportar_ejemplares_csv = accion_exportar_csv(
    'ejemplares',
    ['Código de barras', 'Título', 'Ubicación', 'Estado', 'Fecha de adquisición'],
    lambda e: [e.codigo_barras, e.registro.titulo, e.ubicacion, e.get_estado_display(), e.fecha_adquisicion or ''],
)


@admin.register(Ejemplar)
class EjemplarAdmin(admin.ModelAdmin):
    list_display = ('codigo_barras', 'registro', 'ubicacion', 'estado')
    list_filter = ('estado',)
    search_fields = ('codigo_barras', 'registro__titulo')
    actions = [exportar_ejemplares_csv]


class ConstanciaDonacionLibroInline(admin.TabularInline):
    model = ConstanciaDonacionLibro
    extra = 1
    autocomplete_fields = ['registro']


@admin.register(ConstanciaDonacion)
class ConstanciaDonacionAdmin(admin.ModelAdmin):
    list_display = ('folio', 'persona_nombre', 'cargo', 'fecha', 'total_volumenes', 'generado_por')
    search_fields = ('persona_nombre', 'cargo')
    readonly_fields = ('generado_por',)
    inlines = [ConstanciaDonacionLibroInline]
    actions = ['descargar_word']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.generado_por = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description='Descargar constancia (Word)')
    def descargar_word(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Selecciona una sola constancia.', level=messages.WARNING)
            return
        constancia = queryset.first()
        doc = generar_constancia_donacion_docx(constancia)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{constancia.folio}.docx"'
        doc.save(response)
        return response
