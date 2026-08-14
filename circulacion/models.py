"""Prestamo.marcar_devuelto() y marcar_perdido() usan
Prestamo.objects.filter(pk=...).update(...) en vez de self.save(), para
mantener el lock de select_for_update() vivo durante toda la transacción.
Como .update() nunca dispara la señal post_save, Prestamo queda fuera del
mecanismo genérico de señales de auditoría (alumnos/catalogo/deteccion_libros
usan <app>/signals.py) y en su lugar llama a auditoria.services.registrar()
explícitamente (ver circulacion/services.py:crear_prestamo, y
marcar_devuelto/marcar_perdido más abajo)."""

import datetime

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from auditoria.services import registrar
from catalogo.models import Ejemplar

PLAZO_PRESTAMO_DIAS = 7
TARIFA_MULTA_DIA = 20  # pesos por día de atraso


def _salida_por_defecto():
    return timezone.localdate()


def _devolucion_por_defecto():
    return timezone.localdate() + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS)


# Alias histórico: las migraciones 0002/0003 referencian esta función por
# nombre como default de campo; se conserva para que Django pueda seguir
# resolviéndola al reconstruir el historial de migraciones, aunque el campo
# actual (fecha_devolucion) ya use _devolucion_por_defecto.
_vencimiento_por_defecto = _devolucion_por_defecto


class Prestamo(models.Model):
    """Un préstamo agrupa uno o varios libros (Ejemplar) bajo un solo folio,
    con una única fecha de salida/devolución para todo el grupo."""

    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('DEVUELTO', 'Devuelto'),
        ('PERDIDO', 'Perdido'),
    ]

    folio = models.CharField(max_length=20, unique=True, editable=False)

    # Enlace opcional al Alumno ya registrado (se resuelve por matrícula al
    # crear el préstamo); alumno_nombre/matricula/telefono/carrera quedan
    # siempre como texto libre para que también funcione con alumnos que no
    # están dados de alta en el sistema (préstamo de mostrador).
    alumno = models.ForeignKey(
        'alumnos.Alumno', on_delete=models.SET_NULL, null=True, blank=True, related_name='prestamos'
    )
    alumno_nombre = models.CharField('Nombre del alumno', max_length=200)
    matricula = models.CharField(max_length=20, blank=True, default='')
    telefono = models.CharField(max_length=20, blank=True, default='')
    carrera = models.CharField(max_length=150, blank=True, default='')

    fecha_prestamo = models.DateTimeField(auto_now_add=True)
    fecha_salida = models.DateField('Fecha de salida', default=_salida_por_defecto)
    fecha_devolucion = models.DateField('Fecha de devolución', default=_devolucion_por_defecto)
    fecha_devolucion_real = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVO')
    observaciones = models.TextField(blank=True, default='')

    dias_retraso = models.PositiveIntegerField(default=0)
    multa_total = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    multa_descuento = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    multa_cobrada = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    multa_pagada = models.BooleanField(default=False)
    multa_pagada_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_prestamo']

    @property
    def vencido(self):
        return self.estado == 'ACTIVO' and self.fecha_devolucion < timezone.localdate()

    def marcar_devuelto(self, multa_descuento=0, multa_cobrada=0, multa_pagada=False):
        # Ver nota del módulo: .update() bajo lock, auditado explícitamente.
        # dias_retraso/multa_total se calculan aquí (no se reciben como
        # parámetro) para que siempre reflejen la fecha real de devolución;
        # multa_descuento/multa_cobrada/multa_pagada sí los captura quien
        # atiende la devolución (ver circulacion/admin.py, registrar_devolucion).
        with transaction.atomic():
            prestamo = Prestamo.objects.select_for_update().get(pk=self.pk)
            if prestamo.estado != 'ACTIVO':
                raise ValidationError('Este préstamo ya no está activo.')
            dias_retraso = max(0, (timezone.localdate() - prestamo.fecha_devolucion).days)
            multa_total = dias_retraso * TARIFA_MULTA_DIA
            Prestamo.objects.filter(pk=self.pk).update(
                estado='DEVUELTO', fecha_devolucion_real=timezone.now(),
                dias_retraso=dias_retraso, multa_total=multa_total,
                multa_descuento=multa_descuento, multa_cobrada=multa_cobrada,
                multa_pagada=multa_pagada,
                multa_pagada_at=timezone.now() if multa_pagada else None,
            )
            Ejemplar.objects.filter(pk__in=prestamo.libros.values_list('ejemplar_id', flat=True)).update(
                estado='DISPONIBLE'
            )
        self.refresh_from_db()
        registrar(self, 'MODIFICAR')

    def marcar_perdido(self):
        # Mismo motivo que marcar_devuelto(): .update() bajo lock, sin
        # post_save, auditado explícitamente aquí.
        with transaction.atomic():
            prestamo = Prestamo.objects.select_for_update().get(pk=self.pk)
            if prestamo.estado != 'ACTIVO':
                raise ValidationError('Este préstamo ya no está activo.')
            Prestamo.objects.filter(pk=self.pk).update(estado='PERDIDO')
            Ejemplar.objects.filter(pk__in=prestamo.libros.values_list('ejemplar_id', flat=True)).update(
                estado='PERDIDO'
            )
        self.refresh_from_db()
        registrar(self, 'MODIFICAR')

    def __str__(self):
        return f'{self.folio} — {self.alumno_nombre}'


class PrestamoLibro(models.Model):
    prestamo = models.ForeignKey(Prestamo, on_delete=models.CASCADE, related_name='libros')
    ejemplar = models.ForeignKey('catalogo.Ejemplar', on_delete=models.PROTECT, related_name='prestamos_folio')

    class Meta:
        unique_together = [('prestamo', 'ejemplar')]

    def __str__(self):
        return f'{self.ejemplar} en {self.prestamo.folio}'
