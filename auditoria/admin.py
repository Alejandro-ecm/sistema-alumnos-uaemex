from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'accion', 'content_type', 'objeto_repr', 'usuario')
    list_filter = ('accion', 'content_type', 'fecha_hora')
    search_fields = ('objeto_repr',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
