from django.conf import settings
from django.db import models
from django.utils import timezone


class Autor(models.Model):
    nombre = models.CharField(
        max_length=200,
        help_text="Formato recomendado: 'Apellido, Nombre' — se usa tal cual en los campos MARC 100/700.",
    )

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Editorial(models.Model):
    nombre = models.CharField(max_length=200)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'Editoriales'

    def __str__(self):
        return self.nombre


class Materia(models.Model):
    nombre = models.CharField(max_length=200, unique=True)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'Materias'

    def __str__(self):
        return self.nombre


class RegistroBibliografico(models.Model):
    titulo = models.CharField(max_length=300)
    subtitulo = models.CharField(max_length=300, blank=True)
    isbn = models.CharField(max_length=20, blank=True)
    edicion = models.CharField(max_length=100, blank=True)
    anio_publicacion = models.PositiveIntegerField(null=True, blank=True)
    lugar_publicacion = models.CharField(max_length=150, blank=True)
    idioma = models.CharField(max_length=50, blank=True, default='Español')
    descripcion_fisica = models.CharField(max_length=200, blank=True)
    clasificacion = models.CharField(max_length=50, blank=True)
    notas = models.TextField(blank=True)
    marc_xml = models.TextField(blank=True)

    editorial = models.ForeignKey(
        Editorial, on_delete=models.SET_NULL, null=True, blank=True, related_name='registros'
    )
    autores = models.ManyToManyField(Autor, through='AutorRegistro', related_name='registros')
    materias = models.ManyToManyField(Materia, related_name='registros', blank=True)

    fecha_alta = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Registro bibliográfico'
        verbose_name_plural = 'Registros bibliográficos'

    def __str__(self):
        return self.titulo


class AutorRegistro(models.Model):
    ROLES = [
        ('PRINCIPAL', 'Autor principal'),
        ('COAUTOR', 'Coautor'),
        ('EDITOR', 'Editor'),
        ('TRADUCTOR', 'Traductor'),
        ('COMPILADOR', 'Compilador'),
    ]

    registro = models.ForeignKey(RegistroBibliografico, on_delete=models.CASCADE)
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)
    rol = models.CharField(max_length=20, choices=ROLES, default='PRINCIPAL')
    orden = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['orden']
        unique_together = [('registro', 'autor')]
        verbose_name = 'Autor de registro'
        verbose_name_plural = 'Autores de registro'

    def __str__(self):
        return f'{self.autor} ({self.get_rol_display()}) — {self.registro}'


class Ejemplar(models.Model):
    ESTADOS = [
        ('DISPONIBLE', 'Disponible'),
        ('PRESTADO', 'Prestado'),
        ('PERDIDO', 'Perdido'),
        ('REPARACION', 'En reparación'),
    ]

    registro = models.ForeignKey(RegistroBibliografico, on_delete=models.CASCADE, related_name='ejemplares')
    codigo_barras = models.CharField(max_length=50, unique=True)
    ubicacion = models.CharField(max_length=150, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='DISPONIBLE')
    fecha_adquisicion = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f'{self.codigo_barras} — {self.registro.titulo}'


class ConstanciaDonacion(models.Model):
    persona_nombre = models.CharField(max_length=200)
    cargo = models.CharField(max_length=200, blank=True)
    fecha = models.DateField(default=timezone.now)
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    fecha_alta = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_alta']
        verbose_name = 'Constancia de donación'
        verbose_name_plural = 'Constancias de donación'

    @property
    def folio(self):
        return f'CONST-{self.pk:06d}'

    @property
    def total_volumenes(self):
        return sum(item.cantidad for item in self.libros.all())

    def __str__(self):
        return f'{self.folio} — {self.persona_nombre}'


class ConstanciaDonacionLibro(models.Model):
    constancia = models.ForeignKey(ConstanciaDonacion, on_delete=models.CASCADE, related_name='libros')
    registro = models.ForeignKey(RegistroBibliografico, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [('constancia', 'registro')]
        verbose_name = 'Libro de constancia'
        verbose_name_plural = 'Libros de constancia'

    def __str__(self):
        return f'{self.registro.titulo} × {self.cantidad}'
