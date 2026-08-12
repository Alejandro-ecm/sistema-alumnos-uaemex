from dataclasses import dataclass

from django.db.models import Count
from django.utils import timezone

from .models import ConstanciaDonacion, RegistroBibliografico


def top_libros(limite: int = 5):
    return (
        RegistroBibliografico.objects.annotate(veces_prestado=Count('ejemplares__prestamos'))
        .filter(veces_prestado__gt=0)
        .order_by('-veces_prestado')[:limite]
    )


@dataclass
class ActividadMensual:
    libros_mes_actual: int
    libros_mes_anterior: int
    constancias_mes_actual: int
    constancias_mes_anterior: int


def actividad_mensual() -> ActividadMensual:
    hoy = timezone.now()
    anio_actual, mes_actual = hoy.year, hoy.month
    if mes_actual == 1:
        anio_anterior, mes_anterior = anio_actual - 1, 12
    else:
        anio_anterior, mes_anterior = anio_actual, mes_actual - 1

    return ActividadMensual(
        libros_mes_actual=RegistroBibliografico.objects.filter(
            fecha_alta__year=anio_actual, fecha_alta__month=mes_actual
        ).count(),
        libros_mes_anterior=RegistroBibliografico.objects.filter(
            fecha_alta__year=anio_anterior, fecha_alta__month=mes_anterior
        ).count(),
        constancias_mes_actual=ConstanciaDonacion.objects.filter(
            fecha_alta__year=anio_actual, fecha_alta__month=mes_actual
        ).count(),
        constancias_mes_anterior=ConstanciaDonacion.objects.filter(
            fecha_alta__year=anio_anterior, fecha_alta__month=mes_anterior
        ).count(),
    )
