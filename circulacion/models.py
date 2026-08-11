"""Prestamo.marcar_devuelto() y marcar_perdido() usan
Prestamo.objects.filter(pk=...).update(...) en vez de self.save(), para
mantener el lock de select_for_update() vivo durante toda la transacción.
Como .update() nunca dispara la señal post_save, Prestamo queda fuera del
mecanismo genérico de señales de auditoría (alumnos/catalogo/deteccion_libros
usan <app>/signals.py) y en su lugar llama a auditoria.services.registrar()
explícitamente en save(), marcar_devuelto() y marcar_perdido()."""

import datetime

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from auditoria.services import registrar
from catalogo.models import Ejemplar

PLAZO_PRESTAMO_DIAS = 7


def _vencimiento_por_defecto():
    return timezone.now().date() + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS)


class Prestamo(models.Model):
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('DEVUELTO', 'Devuelto'),
        ('PERDIDO', 'Perdido'),
    ]

    ejemplar = models.ForeignKey('catalogo.Ejemplar', on_delete=models.PROTECT, related_name='prestamos')
    alumno = models.ForeignKey(
        'alumnos.Alumno', on_delete=models.SET_NULL, null=True, blank=True, related_name='prestamos'
    )
    fecha_prestamo = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(default=_vencimiento_por_defecto)
    fecha_devolucion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVO')

    class Meta:
        ordering = ['-fecha_prestamo']

    @property
    def vencido(self):
        return self.estado == 'ACTIVO' and self.fecha_vencimiento < timezone.now().date()

    def clean(self):
        if self._state.adding and self.ejemplar_id:
            if Ejemplar.objects.get(pk=self.ejemplar_id).estado != 'DISPONIBLE':
                raise ValidationError({'ejemplar': 'Este ejemplar ya no está disponible para préstamo.'})

    def save(self, *args, **kwargs):
        if not self._state.adding:
            return super().save(*args, **kwargs)
        with transaction.atomic():
            ejemplar = Ejemplar.objects.select_for_update().get(pk=self.ejemplar_id)
            if ejemplar.estado != 'DISPONIBLE':
                raise ValidationError('Este ejemplar ya no está disponible para préstamo.')
            super().save(*args, **kwargs)
            Ejemplar.objects.filter(pk=ejemplar.pk).update(estado='PRESTADO')
        registrar(self, 'CREAR')

    def marcar_devuelto(self):
        # Se usa .update() (no .save()) para mantener el lock de
        # select_for_update() durante toda la transacción; por eso .update()
        # nunca dispara post_save y esta acción se audita explícitamente en
        # vez de depender de una señal genérica (ver auditoria/services.py).
        with transaction.atomic():
            prestamo = Prestamo.objects.select_for_update().get(pk=self.pk)
            if prestamo.estado != 'ACTIVO':
                raise ValidationError('Este préstamo ya no está activo.')
            Prestamo.objects.filter(pk=self.pk).update(estado='DEVUELTO', fecha_devolucion=timezone.now())
            Ejemplar.objects.filter(pk=self.ejemplar_id).update(estado='DISPONIBLE')
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
            Ejemplar.objects.filter(pk=self.ejemplar_id).update(estado='PERDIDO')
        self.refresh_from_db()
        registrar(self, 'MODIFICAR')

    def __str__(self):
        return f'{self.ejemplar} → {self.alumno}'
