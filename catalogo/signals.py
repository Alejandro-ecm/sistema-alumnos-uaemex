from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from alumnos.models import Alumno
from auditoria.services import registrar

from .models import Ejemplar, RegistroBibliografico
from .services import sincronizar_registro_desde_alumno


@receiver(post_save, sender=Alumno)
def _sincronizar_catalogo_desde_alumno(sender, instance, **kwargs):
    sincronizar_registro_desde_alumno(instance)


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
