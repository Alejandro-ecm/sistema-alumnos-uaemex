from django.contrib import admin
from django.contrib.auth.models import Group
from django.urls import reverse
from .models import Alumno, ImpresionConstancia
from django.utils.html import format_html, format_html_join, mark_safe

from proyecto.admin_utils import accion_exportar_csv

admin.site.unregister(Group)


exportar_alumnos_csv = accion_exportar_csv(
    'alumnos',
    ['Número de cuenta', 'Nombre', 'Facultad', 'Carrera', 'Semestre', 'Modalidad', 'Estado', 'Correo', 'Teléfono'],
    lambda a: [
        a.numero_cuenta, a.nombre, a.get_facultad_display(), a.get_carrera_display(),
        a.semestre or '', a.modalidad or '', a.get_estado_display(), a.correo or '', a.telefono or '',
    ],
)


class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'numero_cuenta', 'facultad', 'carrera', 'semestre', 'estado', 'estado_biblioteca', 'documentos_links', 'ver_pdfs', 'eliminar_btn')
    search_fields = ('nombre', 'numero_cuenta', 'correo')
    list_filter = ('facultad', 'estado', 'carrera', 'semestre', 'modalidad')
    list_editable = ('estado',)
    change_list_template = 'admin/alumnos/alumno/change_list.html'
    actions = [exportar_alumnos_csv]

    fieldsets = (
        ("Datos personales", {
            'fields': ('nombre', 'numero_cuenta', 'correo', 'telefono', 'domicilio')
        }),
        ("Información académica", {
            'fields': ('facultad', 'carrera', 'semestre', 'modalidad', 'tema', 'director')
        }),
        ("Documentos", {
            'fields': ('documento1', 'documento2', 'documento3')
        }),
        ("Control", {
            'fields': ('estado', 'acepta_terminos')
        }),
    )

    def documentos_links(self, obj):
        # format_html/format_html_join escapan el nombre/ruta del archivo
        # (dato que viene de lo que subió el alumno) antes de insertarlo en
        # el atributo href, evitando que un nombre de archivo con comillas
        # u otros caracteres pueda inyectar HTML/JS en el admin.
        documentos = [
            (obj.documento1, 'Doc 1'),
            (obj.documento2, 'Doc 2'),
            (obj.documento3, 'Doc 3'),
        ]
        links = [(doc.url, etiqueta) for doc, etiqueta in documentos if doc]
        if not links:
            return '—'
        return format_html_join(
            mark_safe(' &nbsp; '),
            '<a href="{}" target="_blank">📄 {}</a>',
            links,
        )
    documentos_links.short_description = "Documentos"

    def estado_biblioteca(self, obj):
        from circulacion.services import no_adeudo
        resultado = no_adeudo(obj)
        if resultado.sin_adeudo:
            return mark_safe('<span style="color:#2e7d32;">✅ Sin adeudo</span>')
        return format_html(
            '<span style="color:#c62828;">⚠️ {} vencido(s)</span>', len(resultado.prestamos_vencidos)
        )
    estado_biblioteca.short_description = "Biblioteca"

    def ver_pdfs(self, obj):
        html = (
            f'<div style="display:flex;flex-direction:column;gap:4px;min-width:180px;">'
            f'  <a href="/pdf/{obj.id}/"   target="_blank" style="'
            f'     display:block;padding:4px 8px;background:#2e7d32;color:#fff;'
            f'     border-radius:4px;text-decoration:none;font-size:12px;text-align:center;">'
            f'     🖨 Constancia No Adeudo</a>'
            f'  <a href="/pdf2/{obj.id}/"  target="_blank" style="'
            f'     display:block;padding:4px 8px;background:#1565c0;color:#fff;'
            f'     border-radius:4px;text-decoration:none;font-size:12px;text-align:center;">'
            f'     📋 Registro Material</a>'
            f'  <a href="/carta/{obj.id}/" target="_blank" style="'
            f'     display:block;padding:4px 8px;background:#6a1b9a;color:#fff;'
            f'     border-radius:4px;text-decoration:none;font-size:12px;text-align:center;">'
            f'     📄 Carta Autorización</a>'
            f'</div>'
        )
        return mark_safe(html)
    ver_pdfs.short_description = "Imprimir (Word)"

    def eliminar_btn(self, obj):
        url = reverse('admin:alumnos_alumno_delete', args=[obj.pk])
        html = (
            f'<a href="{url}" style="'
            f'display:block;padding:4px 8px;background:#c62828;color:#fff;'
            f'border-radius:4px;text-decoration:none;font-size:12px;text-align:center;'
            f'min-width:90px;">'
            f'🗑 Eliminar</a>'
        )
        return mark_safe(html)
    eliminar_btn.short_description = "Eliminar"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['total_alumnos'] = Alumno.objects.count()
        extra_context['total_impresiones'] = ImpresionConstancia.objects.count()
        from circulacion.services import alumnos_con_adeudo_count
        extra_context['total_adeudos'] = alumnos_con_adeudo_count()
        return super().changelist_view(request, extra_context=extra_context)


admin.site.register(Alumno, AlumnoAdmin)
