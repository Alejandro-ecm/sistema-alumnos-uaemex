from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class RegistroAuditoria(models.Model):
    """Bitácora de auditoría genérica. Se llena vía auditoria.services.registrar(),
    ya sea automáticamente por señales post_save/post_delete (ver <app>/signals.py)
    o explícitamente donde el modelo modifica filas sin pasar por save()/delete()
    (ver circulacion/models.py, Prestamo)."""

    ACCIONES = [
        ('CREAR', 'Crear'),
        ('MODIFICAR', 'Modificar'),
        ('ELIMINAR', 'Eliminar'),
    ]

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    objeto = GenericForeignKey('content_type', 'object_id')
    objeto_repr = models.CharField(max_length=255)
    accion = models.CharField(max_length=10, choices=ACCIONES)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='registros_auditoria',
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_hora']
        verbose_name = 'Registro de auditoría'
        verbose_name_plural = 'Registros de auditoría'

    def __str__(self):
        return f'{self.get_accion_display()} · {self.objeto_repr}'
