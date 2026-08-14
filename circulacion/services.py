import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from auditoria.services import registrar
from catalogo.models import Ejemplar

from .models import PLAZO_PRESTAMO_DIAS, Prestamo, PrestamoLibro


def _siguiente_folio():
    yyyymm = timezone.localdate().strftime('%Y%m')
    prefijo = f'PREST-{yyyymm}-'
    ultimo_folio = (
        Prestamo.objects.filter(folio__startswith=prefijo)
        .order_by('-folio').values_list('folio', flat=True).first()
    )
    siguiente = int(ultimo_folio[-4:]) + 1 if ultimo_folio else 1
    return f'{prefijo}{siguiente:04d}'


def crear_prestamo(*, alumno_nombre, matricula='', telefono='', carrera='',
                    fecha_salida=None, fecha_devolucion=None, observaciones='', ejemplar_ids):
    """Único punto de entrada para registrar un préstamo (varios libros bajo
    un mismo folio). Si la matrícula coincide con un Alumno ya registrado en
    el sistema, el préstamo queda enlazado a él (para el conteo de adeudos);
    si no, igual se guarda con los datos de texto capturados a mano."""
    from alumnos.models import Alumno

    if not ejemplar_ids:
        raise ValidationError('Agrega al menos un libro al préstamo.')

    fecha_salida = fecha_salida or timezone.localdate()
    fecha_devolucion = fecha_devolucion or (fecha_salida + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS))

    with transaction.atomic():
        ejemplares = list(Ejemplar.objects.select_for_update().filter(pk__in=ejemplar_ids))
        if len(ejemplares) != len(set(ejemplar_ids)):
            raise ValidationError('Alguno de los libros seleccionados ya no existe.')
        no_disponibles = [e for e in ejemplares if e.estado != 'DISPONIBLE']
        if no_disponibles:
            nombres = ', '.join(str(e) for e in no_disponibles)
            raise ValidationError(f'Estos ejemplares ya no están disponibles: {nombres}.')

        alumno = Alumno.objects.filter(numero_cuenta=matricula).first() if matricula else None

        prestamo = Prestamo.objects.create(
            folio=_siguiente_folio(), alumno=alumno, alumno_nombre=alumno_nombre,
            matricula=matricula, telefono=telefono, carrera=carrera,
            fecha_salida=fecha_salida, fecha_devolucion=fecha_devolucion,
            observaciones=observaciones,
        )
        PrestamoLibro.objects.bulk_create(
            PrestamoLibro(prestamo=prestamo, ejemplar=e) for e in ejemplares
        )
        Ejemplar.objects.filter(pk__in=[e.pk for e in ejemplares]).update(estado='PRESTADO')

    registrar(prestamo, 'CREAR')
    return prestamo


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
            alumno=alumno, estado='ACTIVO', fecha_devolucion__lt=timezone.localdate()
        ).prefetch_related('libros__ejemplar__registro')
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
    vencidos = activos_qs.filter(fecha_devolucion__lt=timezone.localdate()).count()
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
        .select_related('alumno')
        .order_by('-fecha_devolucion_real')[:limite]
    )


def multas_por_libro():
    return (
        PrestamoLibro.objects.filter(prestamo__multa_total__gt=0)
        .values('ejemplar__registro__titulo')
        .annotate(total_multas=Sum('prestamo__multa_total'), veces=Count('id'))
        .order_by('-total_multas')
    )


def alumnos_con_adeudo_count() -> int:
    vencidos = Prestamo.objects.filter(
        estado='ACTIVO', fecha_devolucion__lt=timezone.localdate()
    ).only('id', 'alumno_id', 'matricula', 'alumno_nombre')
    identificadores = {p.alumno_id or p.matricula or p.alumno_nombre for p in vencidos}
    return len(identificadores)
