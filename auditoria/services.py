"""Punto de entrada único para escribir en la bitácora: lo llaman las señales
post_save/post_delete de alumnos/catalogo/deteccion_libros, y explícitamente
circulacion.models.Prestamo (ver el docstring de ese módulo)."""

from django.contrib.contenttypes.models import ContentType

from .middleware import get_current_user
from .models import RegistroAuditoria


def registrar(instancia, accion, usuario=None):
    # Comando, no consulta: a diferencia de circulacion/services.py (funciones
    # puras + dataclass), esta función escribe. Devuelve la instancia creada.
    return RegistroAuditoria.objects.create(
        content_type=ContentType.objects.get_for_model(type(instancia)),
        object_id=instancia.pk,
        objeto_repr=str(instancia),
        accion=accion,
        usuario=usuario or get_current_user(),
    )
