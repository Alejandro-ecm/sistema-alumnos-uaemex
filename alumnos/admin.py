from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from .models import Alumno, ImpresionConstancia
from django.utils.html import format_html, format_html_join, mark_safe

admin.site.unregister(Group)
admin.site.unregister(User)

ROLES = ['Administrativos', 'Mantenimiento', 'Bibliotecario']


class UsuarioCreationForm(UserCreationForm):
    """Alta simplificada: usuario, contraseña (x2), rol y si queda activo.
    Oculta is_staff/is_superuser — cualquier cuenta creada aquí entra a
    /admin/ con el rol elegido, nada más (los superusuarios se manejan
    fuera de esta pantalla, p. ej. con `manage.py createsuperuser`)."""

    rol = forms.ChoiceField(choices=[(r, r) for r in ROLES], label='Rol')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'is_active')


class UsuarioChangeForm(UserChangeForm):
    rol = forms.ChoiceField(choices=[(r, r) for r in ROLES], label='Rol', required=False)

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            grupo_actual = self.instance.groups.filter(name__in=ROLES).first()
            self.fields['rol'].initial = grupo_actual.name if grupo_actual else None


@admin.register(User)
class UsuarioAdmin(DjangoUserAdmin):
    add_form = UsuarioCreationForm
    form = UsuarioChangeForm
    list_display = ('username', 'rol_selector', 'is_active', 'last_login', 'eliminar_btn')
    search_fields = ('username',)
    ordering = ('username',)
    filter_horizontal = ()
    actions = None

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'rol', 'is_active'),
        }),
    )
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Rol y acceso', {'fields': ('rol', 'is_active')}),
    )

    def get_urls(self):
        propias = [
            path(
                '<int:user_id>/cambiar-rol/',
                self.admin_site.admin_view(self.cambiar_rol_view),
                name='auth_user_cambiar_rol',
            ),
        ]
        return propias + super().get_urls()

    def cambiar_rol_view(self, request, user_id):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not request.user.has_perm('auth.change_user'):
            return HttpResponseForbidden()
        usuario = get_object_or_404(User, pk=user_id)
        rol = request.POST.get('rol', '')
        usuario.groups.set([Group.objects.get(name=rol)] if rol in ROLES else [])
        return HttpResponse('OK')

    @admin.display(description='Rol')
    def rol_selector(self, obj):
        grupo_actual = obj.groups.filter(name__in=ROLES).first()
        actual = grupo_actual.name if grupo_actual else ''
        url = reverse('admin:auth_user_cambiar_rol', args=[obj.pk])
        opciones = ''.join(
            f'<option value="{r}"{" selected" if r == actual else ""}>{r}</option>' for r in ROLES
        )
        js = (
            "fetch('%s',{method:'POST',headers:{'X-CSRFToken':document.cookie.match(/csrftoken=([^;]+)/)[1]},"
            "body:new URLSearchParams({rol:this.value})}).then(()=>location.reload());"
        ) % url
        html = (
            f'<select onchange="{js}" style="padding:3px 6px;border-radius:4px;border:1px solid #ccc;">'
            f'<option value=""{" selected" if not actual else ""}>— sin rol —</option>'
            f'{opciones}'
            f'</select>'
        )
        return mark_safe(html)

    def eliminar_btn(self, obj):
        url = reverse('admin:auth_user_delete', args=[obj.pk])
        html = (
            f'<a href="{url}" style="'
            f'display:block;padding:4px 8px;background:#c62828;color:#fff;'
            f'border-radius:4px;text-decoration:none;font-size:12px;text-align:center;'
            f'min-width:90px;">'
            f'🗑 Eliminar</a>'
        )
        return mark_safe(html)
    eliminar_btn.short_description = "Eliminar"

    def save_model(self, request, obj, form, change):
        obj.is_staff = True
        super().save_model(request, obj, form, change)
        rol = form.cleaned_data.get('rol')
        obj.groups.set([Group.objects.get(name=rol)] if rol else [])


class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'numero_cuenta', 'facultad', 'carrera', 'semestre', 'estado', 'estado_biblioteca', 'documentos_links', 'ver_pdfs', 'eliminar_btn')
    search_fields = ('nombre', 'numero_cuenta', 'correo')
    list_editable = ('estado',)
    change_list_template = 'admin/alumnos/alumno/change_list.html'
    actions = None

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
