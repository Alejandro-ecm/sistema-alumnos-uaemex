from dataclasses import dataclass
from io import BytesIO

from django.db.models import Count
from django.utils import timezone
from pymarc import MARCReader, MARCWriter, XMLWriter
from pymarc.marcxml import parse_xml_to_array

from .marc import construir_registro_marc, generar_marc_xml, poblar_registro_desde_marc
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


def exportar_marc_coleccion(formato: str) -> bytes:
    """Exporta TODOS los registros bibliográficos como un único archivo MARC21,
    en el formato que Aleph/Voyager esperan para cargas por lote:
    'mrc' = ISO 2709 binario, 'xml' = colección MARCXML.
    """
    buffer = BytesIO()
    writer = MARCWriter(buffer) if formato == 'mrc' else XMLWriter(buffer)
    for registro in RegistroBibliografico.objects.all():
        writer.write(construir_registro_marc(registro))
    writer.close(close_fh=False)
    return buffer.getvalue()


def importar_marc(archivo) -> dict:
    """Importa registros bibliográficos desde un archivo MARC21 (.mrc ISO 2709
    o .xml MARCXML) exportado de otro sistema bibliotecario, p. ej. Aleph o
    Voyager.
    """
    nombre = archivo.name.lower()
    contenido = archivo.read()

    if nombre.endswith('.mrc') or nombre.endswith('.marc'):
        try:
            records = list(MARCReader(BytesIO(contenido), to_unicode=True, force_utf8=True))
        except Exception as e:
            return {'error': f'No se pudo leer el archivo MARC21 (.mrc): {e}'}
    elif nombre.endswith('.xml'):
        try:
            records = parse_xml_to_array(BytesIO(contenido))
        except Exception as e:
            return {'error': f'No se pudo leer el archivo MARC21 (.xml): {e}'}
    else:
        return {'error': 'Formato no soportado. Sube un archivo .mrc o .xml (MARC21).'}

    if not records:
        return {'error': 'El archivo no contiene registros MARC21 válidos.'}

    nuevos = actualizados = errores = 0
    resultados = []
    for n, record in enumerate(records, start=1):
        try:
            registro, creado = poblar_registro_desde_marc(record)
            estado = 'nuevo' if creado else 'actualizado'
            if creado:
                nuevos += 1
            else:
                actualizados += 1
            resultados.append({'fila': n, 'estado': estado, 'titulo': registro.titulo})
        except Exception as e:
            errores += 1
            resultados.append({'fila': n, 'estado': 'error', 'titulo': '—', 'error': str(e)})

    return {'nuevos': nuevos, 'actualizados': actualizados, 'errores': errores, 'resultados': resultados}


def top_libros(limite: int = 5):
    return (
        RegistroBibliografico.objects.annotate(veces_prestado=Count('ejemplares__prestamos_folio'))
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
