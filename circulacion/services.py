from dataclasses import dataclass, field

from django.utils import timezone

from .models import Prestamo


@dataclass
class EstadoAdeudo:
    sin_adeudo: bool
    prestamos_vencidos: list = field(default_factory=list)


def no_adeudo(alumno) -> EstadoAdeudo:
    """Única fuente de verdad sobre préstamos vencidos de un alumno.

    Siempre consultivo: no modifica Alumno ni Prestamo, solo informa.
    """
    vencidos = list(
        Prestamo.objects.filter(
            alumno=alumno, estado='ACTIVO', fecha_vencimiento__lt=timezone.now().date()
        ).select_related('ejemplar__registro')
    )
    return EstadoAdeudo(sin_adeudo=not vencidos, prestamos_vencidos=vencidos)


@dataclass
class ResumenPrestamos:
    activos: int
    vencidos: int


def resumen_prestamos() -> ResumenPrestamos:
    activos_qs = Prestamo.objects.filter(estado='ACTIVO')
    vencidos = activos_qs.filter(fecha_vencimiento__lt=timezone.now().date()).count()
    return ResumenPrestamos(activos=activos_qs.count(), vencidos=vencidos)


def alumnos_con_adeudo_count() -> int:
    return (
        Prestamo.objects.filter(estado='ACTIVO', fecha_vencimiento__lt=timezone.now().date())
        .values('alumno').distinct().count()
    )
