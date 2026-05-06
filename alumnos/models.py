from django.db import models

class Alumno(models.Model):

    CARRERAS = [
        ('MEDICO', 'Lic. Médico Cirujano'),
        ('NUTRICION', 'Lic. Nutrición'),
        ('FISIO', 'Lic. Fisioterapia'),
        ('OCUPACIONAL', 'Lic. Terapia Ocupacional'),
        ('BIOING', 'Lic.Bioingeniería Médica'),
    ]

    SEMESTRES = [
        (1, '1°'), (2, '2°'), (3, '3°'), (4, '4°'),
        (5, '5°'), (6, '6°'), (7, '7°'), (8, '8°'),
    ]

    MODALIDADES = [
        ('ARTICULO', 'Artículo especializado para publicar en revista indizada'),
        ('CREDITOS', 'Créditos en Estudios Avanzados'),
        ('ENSAYO', 'Ensayo'),
        ('TESIS', 'Tesis'),
        ('TESINA', 'Tesina'),
        ('REPORTE_CONOCIMIENTOS', 'Reporte de aplicación de conocimientos'),
        ('REPORTE_SOCIAL', 'Reporte de servicio social en el Área de la Salud'),
        ('REPORTE_RESIDENCIA', 'Reporte de residencia de investigación'),
    ]

    ESTADOS = [
        ('Pendiente', 'Pendiente'),
        ('En revisión', 'En revisión'),
        ('Revisado', 'Revisado'),
        ('Aprobado', 'Aprobado'),
        ('Rechazado', 'Rechazado'),
    ]

    # Datos personales
    nombre = models.CharField(max_length=100)
    numero_cuenta = models.CharField(max_length=20)
    correo = models.EmailField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    domicilio = models.CharField(max_length=200, blank=True, null=True)

    # Datos académicos
    carrera = models.CharField(max_length=20, choices=CARRERAS)
    semestre = models.IntegerField(choices=SEMESTRES, blank=True, null=True)
    modalidad = models.CharField(max_length=30, choices=MODALIDADES, blank=True, null=True)
    tema = models.TextField(blank=True, null=True)
    director = models.CharField(max_length=150, blank=True, null=True)

    # Documentos
    documento1 = models.FileField(upload_to='documentos/', blank=True, null=True)
    documento2 = models.FileField(upload_to='documentos/', blank=True, null=True)
    documento3 = models.FileField(upload_to='documentos/', blank=True, null=True)

    FACULTADES = [
        ('MEDICINA', 'Facultad de Medicina'),
        ('QUIMICA', 'Facultad de Química'),
    ]

    facultad = models.CharField(max_length=20, choices=FACULTADES, default='MEDICINA')

    # Control
    estado = models.CharField(max_length=20, choices=ESTADOS, default='Pendiente')
    acepta_terminos = models.BooleanField(default=False)
    fecha_registro = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.nombre