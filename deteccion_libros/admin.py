import json
from pathlib import Path

from django.contrib import admin
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from .models import EventoDeteccion

RUTA_CAMARAS = Path(__file__).resolve().parent / 'vision' / 'camaras.json'
PUERTO_STREAM = 8090


def _leer_camaras():
    try:
        with open(RUTA_CAMARAS, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _guardar_camaras(camaras):
    with open(RUTA_CAMARAS, 'w', encoding='utf-8') as f:
        json.dump(camaras, f, indent=4, ensure_ascii=False)


@admin.register(EventoDeteccion)
class EventoDeteccionAdmin(admin.ModelAdmin):
    list_display = ('miniatura', 'tipo_badge', 'fuente', 'confianza_pct', 'fecha_hora', 'alumno', 'revisado')
    list_editable = ('revisado',)
    list_filter = ('tipo', 'fuente', 'revisado', 'fecha_hora')
    search_fields = ('fuente', 'notas', 'alumno__nombre')
    readonly_fields = ('vista_previa', 'fecha_hora')
    fieldsets = (
        ('Evento', {
            'fields': ('tipo', 'fuente', 'confianza', 'fecha_hora')
        }),
        ('Evidencia', {
            'fields': ('vista_previa', 'imagen_evidencia', 'clip_evidencia')
        }),
        ('Seguimiento', {
            'fields': ('alumno', 'revisado', 'notas')
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('vista-seguridad/', self.admin_site.admin_view(self.vista_seguridad),
                 name='deteccion_libros_vista_seguridad'),
            path('vista-seguridad/guardar-camara/',
                 self.admin_site.admin_view(self.guardar_camara),
                 name='deteccion_libros_guardar_camara'),
        ]
        return extra + urls

    def vista_seguridad(self, request):
        camaras = _leer_camaras()
        context = {
            **self.admin_site.each_context(request),
            'title': 'Vista de seguridad',
            'camaras': camaras,
            'puerto_stream': PUERTO_STREAM,
        }
        return TemplateResponse(request, 'deteccion_libros/vista_seguridad.html', context)

    @method_decorator(require_POST)
    def guardar_camara(self, request):
        """Crea o actualiza una entrada de camaras.json (fuente + activa) desde el
        panel de Vista de seguridad, para conectar el celular o una cámara de la
        escuela sin editar el archivo a mano. capturar.py detecta el cambio solo
        (mtime-watch en su loop principal) y arranca/detiene el hilo correspondiente."""
        nombre = (request.POST.get('nombre') or '').strip()
        source = (request.POST.get('source') or '').strip()
        activa = request.POST.get('activa') == '1'

        if not nombre or not source:
            return JsonResponse({'ok': False, 'error': 'Nombre y fuente son obligatorios.'}, status=400)

        camaras = _leer_camaras()
        existente = next((c for c in camaras if c['nombre'] == nombre), None)
        if existente:
            existente['source'] = source
            existente['activa'] = activa
        else:
            camaras.append({
                'nombre': nombre,
                'source': source,
                'activa': activa,
                'zona_salida': None,
            })
        _guardar_camaras(camaras)
        return JsonResponse({'ok': True, 'camaras': camaras})

    def miniatura(self, obj):
        if obj.imagen_evidencia:
            return format_html(
                '<img src="{}" style="width:56px;height:56px;object-fit:cover;border-radius:8px;'
                'box-shadow:0 2px 6px rgba(0,0,0,.25);">', obj.imagen_evidencia.url
            )
        return '—'
    miniatura.short_description = 'Evidencia'

    def tipo_badge(self, obj):
        color = '#c62828' if obj.tipo == 'robo' else '#b8973a'
        return format_html(
            '<span style="display:inline-block;padding:4px 12px;border-radius:20px;'
            'font-size:12px;font-weight:700;color:#fff;background:{};">{}</span>',
            color, obj.get_tipo_display()
        )
    tipo_badge.short_description = 'Tipo'

    def confianza_pct(self, obj):
        return f'{obj.confianza * 100:.0f}%'
    confianza_pct.short_description = 'Confianza'

    def vista_previa(self, obj):
        if obj.imagen_evidencia:
            return format_html('<img src="{}" style="max-width:420px;border-radius:12px;">', obj.imagen_evidencia.url)
        return 'Sin imagen'
    vista_previa.short_description = 'Vista previa'
