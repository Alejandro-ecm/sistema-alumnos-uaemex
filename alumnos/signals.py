from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from auditoria.services import registrar

from .models import Alumno, ImpresionConstancia


@receiver(post_save, sender=Alumno)
def _auditar_guardado_alumno(sender, instance, created, **kwargs):
    registrar(instance, 'CREAR' if created else 'MODIFICAR')


@receiver(post_delete, sender=Alumno)
def _auditar_borrado_alumno(sender, instance, **kwargs):
    registrar(instance, 'ELIMINAR')


@receiver(post_save, sender=ImpresionConstancia)
def _auditar_guardado_impresion_constancia(sender, instance, created, **kwargs):
    registrar(instance, 'CREAR' if created else 'MODIFICAR')


@receiver(post_delete, sender=ImpresionConstancia)
def _auditar_borrado_impresion_constancia(sender, instance, **kwargs):
    registrar(instance, 'ELIMINAR')
