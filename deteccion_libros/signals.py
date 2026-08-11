from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from auditoria.services import registrar

from .models import EventoDeteccion


@receiver(post_save, sender=EventoDeteccion)
def _auditar_guardado_evento(sender, instance, created, **kwargs):
    registrar(instance, 'CREAR' if created else 'MODIFICAR')


@receiver(post_delete, sender=EventoDeteccion)
def _auditar_borrado_evento(sender, instance, **kwargs):
    registrar(instance, 'ELIMINAR')
