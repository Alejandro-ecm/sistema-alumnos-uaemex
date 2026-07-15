from django.contrib import admin
from django.contrib.auth.models import Group
from .models import Alumno
from django.utils.html import mark_safe

admin.site.unregister(Group)


class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'numero_cuenta', 'facultad', 'carrera', 'semestre', 'estado', 'documentos_links', 'ver_pdfs')
    search_fields = ('nombre', 'numero_cuenta', 'correo')
    list_filter = ('facultad', 'estado', 'carrera', 'semestre', 'modalidad')
    list_editable = ('estado',)

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
        links = []
        if obj.documento1:
            links.append(f'<a href="/media/{obj.documento1}" target="_blank">📄 Doc 1</a>')
        if obj.documento2:
            links.append(f'<a href="/media/{obj.documento2}" target="_blank">📄 Doc 2</a>')
        if obj.documento3:
            links.append(f'<a href="/media/{obj.documento3}" target="_blank">📄 Doc 3</a>')
        return mark_safe(' &nbsp; '.join(links)) if links else '—'
    documentos_links.short_description = "Documentos"

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


admin.site.register(Alumno, AlumnoAdmin)
