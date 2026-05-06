from django.db import models

class Alumno(models.Model):

    CARRERAS = [
        # Medicina – Licenciatura
        ('MEDICO',      'Lic. Médico Cirujano'),
        ('NUTRICION',   'Lic. Nutrición'),
        ('FISIO',       'Lic. Fisioterapia'),
        ('OCUPACIONAL', 'Lic. Terapia Ocupacional'),
        ('BIOING',      'Lic. Bioingeniería Médica'),
        # Química – Licenciatura
        ('QUIMICA',     'Lic. Química'),
        ('QUIM_FARM',   'Lic. Química Farmacéutica Biológica'),
        ('QUIM_ALIM',   'Lic. Química en Alimentos'),
        ('ING_QUIM',    'Lic. Ingeniería Química'),
        ('ING_PETRO',   'Lic. Ingeniería Petroquímica'),
        # Medicina – Especialidades
        ('M_ESP_01',  'Esp. en Urología'),
        ('M_ESP_02',  'Esp. en Medicina de Urgencias'),
        ('M_ESP_03',  'Esp. en Ortopedia'),
        ('M_ESP_04',  'Esp. en Medicina Crítica en Obstetricia'),
        ('M_ESP_05',  'Esp. en Cirugía Maxilofacial'),
        ('M_ESP_06',  'Esp. en Otorrinolaringología'),
        ('M_ESP_07',  'Esp. en Medicina Interna'),
        ('M_ESP_08',  'Esp. en Cirugía General'),
        ('M_ESP_09',  'Esp. en Anestesiología'),
        ('M_ESP_10',  'Esp. en Psiquiatría'),
        ('M_ESP_11',  'Esp. en Cirugía Pediátrica'),
        ('M_ESP_12',  'Esp. en Cirugía Plástica y Reconstructiva'),
        ('M_ESP_13',  'Esp. en Cirugía Oncológica'),
        ('M_ESP_14',  'Esp. en Cardiología'),
        ('M_ESP_15',  'Esp. en Medicina de Rehabilitación'),
        ('M_ESP_16',  'Esp. en Oncología Médica'),
        ('M_ESP_17',  'Esp. en Radiooncología'),
        ('M_ESP_18',  'Esp. en Imagenología Diagnóstica y Terapéutica'),
        ('M_ESP_19',  'Esp. en Neurocirugía'),
        ('M_ESP_20',  'Esp. en Pediatría'),
        ('M_ESP_21',  'Esp. en Ginecología y Obstetricia'),
        ('M_ESP_22',  'Esp. en Medicina Familiar'),
        ('M_ESP_23',  'Esp. en Neonatología'),
        ('M_ESP_24',  'Esp. en Geriatría'),
        ('M_ESP_25',  'Esp. en Cirugía de Tórax General'),
        ('M_ESP_26',  'Esp. en Medicina Crítica'),
        ('M_ESP_27',  'Esp. en Medicina Materno Fetal'),
        ('M_ESP_28',  'Esp. en Medicina del Trabajo y Ambiental'),
        ('M_ESP_29',  'Esp. en Epidemiología'),
        ('M_ESP_30',  'Esp. en Biología de la Reproducción Humana'),
        ('M_ESP_31',  'Esp. en Medicina de la Actividad Física y el Deporte'),
        ('M_ESP_32',  'Esp. en Medicina Legal'),
        ('M_ESP_33',  'Esp. en Salud Pública'),
        # Medicina – Maestrías
        ('M_MST_01',  'Maestría en Ciencias de la Salud'),
        ('M_MST_02',  'Maestría en Física Médica'),
        # Química – Maestrías
        ('Q_MST_01',  'Maestría en Calidad Ambiental'),
        ('Q_MST_02',  'Maestría en Ciencia de Materiales'),
        ('Q_MST_03',  'Maestría en Ciencias Ambientales'),
        ('Q_MST_04',  'Maestría en Ciencias Químicas'),
        ('Q_MST_05',  'Maestría en Ciencias y Tecnología Farmacéuticas'),
        # Química – Doctorados
        ('Q_DOC_01',  'Doctorado en Ciencia de Materiales'),
        ('Q_DOC_02',  'Doctorado en Ciencias Ambientales'),
        ('Q_DOC_03',  'Doctorado en Ciencias Químicas'),
        ('Q_DOC_04',  'Doctorado en Ciencias y Tecnología Farmacéuticas'),
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