from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from auditoria.services import registrar

from .models import Ejemplar, RegistroBibliografico


@receiver(post_save, sender=RegistroBibliografico)
def _auditar_guardado_registro(sender, instance, created, **kwargs):
    registrar(instance, 'CREAR' if created else 'MODIFICAR')


@receiver(post_delete, sender=RegistroBibliografico)
def _auditar_borrado_registro(sender, instance, **kwargs):
    registrar(instance, 'ELIMINAR')


@receiver(post_save, sender=Ejemplar)
def _auditar_guardado_ejemplar(sender, instance, created, **kwargs):
    registrar(instance, 'CREAR' if created else 'MODIFICAR')


@receiver(post_delete, sender=Ejemplar)
def _auditar_borrado_ejemplar(sender, instance, **kwargs):
    registrar(instance, 'ELIMINAR')
