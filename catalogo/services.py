from dataclasses import dataclass

from django.db.models import Count
from django.utils import timezone

from .marc import generar_marc_xml
from .models import Autor, AutorRegistro, ConstanciaDonacion, Editorial, RegistroBibliografico


def sincronizar_registro_desde_alumno(alumno):
    """Crea o actualiza el Registro bibliográfico del catálogo a partir de los
    datos del libro que el alumno llenó en su cuestionario de registro, y
    genera/actualiza su MARC21. No hace nada si el alumno no capturó título.
    """
    if not (alumno.libro_titulo or '').strip():
        return None

    registro = getattr(alumno, 'registro_bibliografico', None) or RegistroBibliografico(alumno=alumno)
    registro.titulo = alumno.libro_titulo.strip()
    registro.edicion = (alumno.libro_edicion or '').strip()

    editorial_nombre = (alumno.libro_editorial or '').strip()
    if editorial_nombre:
        registro.editorial, _ = Editorial.objects.get_or_create(nombre=editorial_nombre)

    registro.save()

    autor_nombre = (alumno.libro_autor or '').strip()
    if autor_nombre:
        autor, _ = Autor.objects.get_or_create(nombre=autor_nombre)
        AutorRegistro.objects.get_or_create(
            registro=registro, autor=autor, defaults={'rol': 'PRINCIPAL', 'orden': 1}
        )

    registro.marc_xml = generar_marc_xml(registro)
    registro.save(update_fields=['marc_xml'])
    return registro


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
