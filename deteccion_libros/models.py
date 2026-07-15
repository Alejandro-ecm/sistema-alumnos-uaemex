from django.db import models

from alumnos.models import Alumno


class EventoDeteccion(models.Model):
    TIPOS = [
        ('robo', 'Posible sustracción de libro'),
        ('ruptura', 'Posible ruptura de páginas'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPOS)
    fuente = models.CharField(max_length=100, help_text='Nombre de la cámara que generó el evento')
    confianza = models.FloatField(help_text='Confianza del modelo/heurística (0.0 a 1.0)')
    imagen_evidencia = models.ImageField(upload_to='detecciones/%Y/%m/')
    clip_evidencia = models.FileField(upload_to='detecciones/clips/%Y/%m/', blank=True, null=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    revisado = models.BooleanField(default=False)
    notas = models.TextField(blank=True)
    alumno = models.ForeignKey(Alumno, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Evento detectado'
        verbose_name_plural = 'Eventos detectados'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.fuente} ({self.fecha_hora:%Y-%m-%d %H:%M})'
