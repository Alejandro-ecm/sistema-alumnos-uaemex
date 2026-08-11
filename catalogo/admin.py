from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html

from proyecto.admin_utils import accion_exportar_csv

from .constancia_donacion import generar_constancia_donacion_docx
from .marc import generar_marc_xml
from .models import (
    Autor, AutorRegistro, ConstanciaDonacion, ConstanciaDonacionLibro,
    Editorial, Ejemplar, Materia, RegistroBibliografico,
)


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
            path('panel-biblioteca/', self.admin_site.admin_view(self.panel_biblioteca),
                 name='catalogo_panel_biblioteca'),
        ]
        return extra + urls

    def panel_biblioteca(self, request):
        if not request.user.has_perm('catalogo.view_registrobibliografico'):
            raise PermissionDenied
        # import local: catalogo no depende de circulacion a nivel de módulo
        from circulacion.services import resumen_multas, resumen_prestamos
        resumen = resumen_prestamos()
        multas = resumen_multas()
        context = {
            **self.admin_site.each_context(request),
            'title': 'Panel Biblioteca',
            'total_ejemplares': Ejemplar.objects.count(),
            'ejemplares_disponibles': Ejemplar.objects.filter(estado='DISPONIBLE').count(),
            'prestamos_activos': resumen.activos,
            'prestamos_vencidos': resumen.vencidos,
            'libros_recientes': RegistroBibliografico.objects.order_by('-fecha_alta')[:5],
            'constancias_recientes': ConstanciaDonacion.objects.select_related('generado_por')
                .prefetch_related('libros__registro')[:5],
            'constancias_total': ConstanciaDonacion.objects.count(),
            'multas': multas,
        }
        return TemplateResponse(request, 'catalogo/panel_biblioteca.html', context)


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
