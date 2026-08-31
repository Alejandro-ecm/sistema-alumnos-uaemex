from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from auditoria.services import registrar

from .models import Alumno, ImpresionConstancia

User = get_user_model()


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


@receiver(m2m_changed, sender=User.groups.through)
def _sincronizar_is_superuser_con_rol_superusuario(sender, instance, action, **kwargs):
    """El rol 'Superusuario' (alumnos/admin.py) debe dar de verdad todas las
    funciones de superusuario, no solo un conjunto amplio de permisos por
    grupo (eso ya se probó en 0016/0017 y Jazzmin seguía ocultando opciones
    reservadas a is_superuser=True). Este receptor mantiene is_superuser en
    sincronía con la pertenencia al grupo, sin importar por qué vía se
    agregó/quitó (pantalla de rol, shell, fixtures, etc.)."""
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return
    es_superusuario = instance.groups.filter(name='Superusuario').exists()
    if instance.is_superuser != es_superusuario:
        instance.is_superuser = es_superusuario
        instance.save(update_fields=['is_superuser'])
