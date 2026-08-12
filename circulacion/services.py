from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Count, Sum
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
    devueltos: int
    total: int


def resumen_prestamos() -> ResumenPrestamos:
    activos_qs = Prestamo.objects.filter(estado='ACTIVO')
    vencidos = activos_qs.filter(fecha_vencimiento__lt=timezone.now().date()).count()
    devueltos = Prestamo.objects.filter(estado='DEVUELTO').count()
    return ResumenPrestamos(
        activos=activos_qs.count(), vencidos=vencidos, devueltos=devueltos, total=Prestamo.objects.count()
    )


@dataclass
class ResumenMultas:
    con_multa: int
    total_generado: Decimal
    total_cobrado: Decimal
    total_descuentos: Decimal
    pendientes: int


def resumen_multas() -> ResumenMultas:
    con_multa_qs = Prestamo.objects.filter(multa_total__gt=0)
    agregados = con_multa_qs.aggregate(
        generado=Sum('multa_total'), cobrado=Sum('multa_cobrada'), descuentos=Sum('multa_descuento')
    )
    return ResumenMultas(
        con_multa=con_multa_qs.count(),
        total_generado=agregados['generado'] or Decimal('0'),
        total_cobrado=agregados['cobrado'] or Decimal('0'),
        total_descuentos=agregados['descuentos'] or Decimal('0'),
        pendientes=con_multa_qs.filter(multa_pagada=False).count(),
    )


def multas_recientes(limite: int = 15):
    return (
        Prestamo.objects.filter(multa_total__gt=0)
        .select_related('ejemplar__registro', 'alumno')
        .order_by('-fecha_devolucion')[:limite]
    )


def multas_por_libro():
    return (
        Prestamo.objects.filter(multa_total__gt=0)
        .values('ejemplar__registro__titulo')
        .annotate(total_multas=Sum('multa_total'), veces=Count('id'))
        .order_by('-total_multas')
    )


def alumnos_con_adeudo_count() -> int:
    return (
        Prestamo.objects.filter(estado='ACTIVO', fecha_vencimiento__lt=timezone.now().date())
        .values('alumno').distinct().count()
    )
