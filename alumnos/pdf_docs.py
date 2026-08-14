"""Generación de los 3 documentos del alumno en PDF real (no Word), pensados
para adjuntarse por correo y que el propio alumno los pueda imprimir después
de la autorización del personal administrativo. El contenido reproduce el de
las plantillas .docx existentes (templates_docx/) usadas para imprimir desde
el panel, pero construido directamente como PDF con reportlab."""

import datetime
import os
from io import BytesIO

from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

LOGO_PATH = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.JPG')

_stylesheet = getSampleStyleSheet()

ESTILO_TITULO = ParagraphStyle('titulo', parent=_stylesheet['Normal'], fontSize=12, leading=15, alignment=TA_CENTER, spaceAfter=4)
ESTILO_SUBTITULO = ParagraphStyle('subtitulo', parent=_stylesheet['Normal'], fontSize=9, leading=12, alignment=TA_CENTER, spaceAfter=2)
ESTILO_NORMAL = ParagraphStyle('normal', parent=_stylesheet['Normal'], fontSize=10, leading=14)
ESTILO_JUSTIFICADO = ParagraphStyle('justificado', parent=_stylesheet['Normal'], fontSize=10, leading=14, alignment=TA_JUSTIFY)
ESTILO_CENTRADO = ParagraphStyle('centrado', parent=_stylesheet['Normal'], fontSize=10, leading=14, alignment=TA_CENTER)
ESTILO_DERECHA = ParagraphStyle('derecha', parent=_stylesheet['Normal'], fontSize=10, leading=14, alignment=TA_RIGHT)
ESTILO_NEGRITA = ParagraphStyle('negrita', parent=_stylesheet['Normal'], fontSize=10, leading=14, fontName='Helvetica-Bold')
ESTILO_NEGRITA_CENTRO = ParagraphStyle('negrita_centro', parent=_stylesheet['Normal'], fontSize=10, leading=14, fontName='Helvetica-Bold', alignment=TA_CENTER)
ESTILO_NOTA = ParagraphStyle('nota', parent=_stylesheet['Normal'], fontSize=8.5, leading=11)


def _today_str():
    hoy = datetime.date.today()
    return f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


def _safe(value, default=''):
    return (value or default).strip()


def _logo_flowable(width_in=1.0):
    if not os.path.exists(LOGO_PATH):
        return None
    try:
        reader = ImageReader(LOGO_PATH)
        w, h = reader.getSize()
        width = width_in * inch
        height = width * (h / w)
        img = Image(LOGO_PATH, width=width, height=height)
        img.hAlign = 'CENTER'
        return img
    except Exception:
        return None


def _encabezado(story):
    logo = _logo_flowable()
    if logo:
        story.append(logo)
        story.append(Spacer(1, 8))
    story.append(Paragraph('Universidad Autónoma del Estado de México', ESTILO_TITULO))
    story.append(Paragraph('Facultad de Medicina y Química — Biblioteca de Área', ESTILO_SUBTITULO))
    story.append(Spacer(1, 14))


def _nuevo_doc(margen=0.9):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=margen * inch, bottomMargin=margen * inch,
        leftMargin=1 * inch, rightMargin=1 * inch,
    )
    return buffer, doc


# ──────────────────────────────────────────────────────────────
# CONSTANCIA NO ADEUDO
# ──────────────────────────────────────────────────────────────

def generar_constancia_pdf(alumno):
    nombre = _safe(alumno.nombre).upper()
    carrera = alumno.get_carrera_display().upper() if alumno.carrera else ''
    cuenta = _safe(alumno.numero_cuenta)
    fecha = _today_str()

    buffer, doc = _nuevo_doc()
    story = []
    _encabezado(story)

    story.append(Paragraph(f'Toluca, México, {fecha}', ESTILO_NORMAL))
    story.append(Spacer(1, 10))
    story.append(Paragraph('M. en E.N.A, BETHSABE HERNANDEZ CRUZ', ESTILO_NEGRITA))
    story.append(Paragraph('ENCARGADO DEL DEPARTAMENTO DE CONTROL ESCOLAR FACULTAD DE MEDICINA', ESTILO_NORMAL))
    story.append(Paragraph('UNIVERSIDAD AUTÓNOMA DEL ESTADO DE MÉXICO', ESTILO_NORMAL))
    story.append(Paragraph('PRESENTE', ESTILO_NORMAL))
    story.append(Spacer(1, 16))

    story.append(Paragraph(
        f'Por medio de la presente hago constar que <b>{nombre}</b>, pasante de la '
        f'<b>{carrera}</b>, con número de cuenta <b>{cuenta}</b>, No adeuda multas ni '
        'material documental en el Sistema Bibliotecario de la UAEM.',
        ESTILO_JUSTIFICADO,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Sin otro particular se extiende la presente, a petición del interesado y '
        'para los trámites a que haya lugar.',
        ESTILO_JUSTIFICADO,
    ))
    story.append(Spacer(1, 16))
    story.append(Paragraph('ATENTAMENTE', ESTILO_CENTRADO))
    story.append(Paragraph('PATRIA, CIENCIA Y TRABAJO', ESTILO_CENTRADO))
    story.append(Paragraph(
        '2026, Conmemoración del ingreso de la científica y académica '
        'Elena Cárdenas Guerrero al Instituto Científico y Literario',
        ESTILO_CENTRADO,
    ))
    story.append(Spacer(1, 40))
    story.append(Paragraph('_' * 60, ESTILO_CENTRADO))
    story.append(Paragraph('P. L.C.I.D. MARCO ANTONIO TOLEDANO LÓPEZ', ESTILO_CENTRADO))
    story.append(Paragraph('COORDINADOR DE LA BIBLIOTECA DE ÁREA', ESTILO_CENTRADO))
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        'DOCUMENTO CONTROLADO EN EL SITIO WEB DEL SGC, QUE SE ENCUENTRA DISPONIBLE '
        'EXCLUSIVAMENTE PARA LA UNIVERSIDAD AUTÓNOMA DEL ESTADO DE MÉXICO. PROHIBIDA '
        'SU REPRODUCCIÓN TOTAL O PARCIAL.',
        ESTILO_NOTA,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer, f'constancia_{cuenta}.pdf'


# ──────────────────────────────────────────────────────────────
# REGISTRO DE MATERIAL
# ──────────────────────────────────────────────────────────────

def generar_registro_material_pdf(alumno):
    nombre = _safe(alumno.nombre).upper()
    cuenta = _safe(alumno.numero_cuenta)
    libro_titulo = _safe(alumno.libro_titulo)
    libro_autor = _safe(alumno.libro_autor)
    libro_edicion = _safe(alumno.libro_edicion)
    libro_editorial = _safe(alumno.libro_editorial)

    buffer, doc = _nuevo_doc()
    story = []
    _encabezado(story)

    story.append(Paragraph(nombre, ESTILO_NEGRITA))
    story.append(Paragraph('PRESENTE', ESTILO_NORMAL))
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        'Agradecemos la donación del material documental correspondiente al título '
        'que a continuación se detalla, mismo que nos hizo llegar y que enriquecerá '
        'el acervo de este Espacio Académico y sin duda será de gran beneficio a la '
        'comunidad universitaria.',
        ESTILO_JUSTIFICADO,
    ))
    story.append(Spacer(1, 14))

    tabla = Table(
        [
            ['Título', 'Autor', 'Edición', 'Editorial'],
            [libro_titulo or '—', libro_autor or '—', libro_edicion or '—', libro_editorial or '—'],
        ],
        colWidths=[1.7 * inch, 1.7 * inch, 1.1 * inch, 1.7 * inch],
    )
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f9d5a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.75, colors.HexColor('#cccccc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 20))

    story.append(Paragraph('Sin otro particular y agradeciendo su apoyo, le envío un cordial saludo.', ESTILO_JUSTIFICADO))
    story.append(Spacer(1, 16))
    story.append(Paragraph('ATENTAMENTE', ESTILO_CENTRADO))
    story.append(Paragraph('Patria, Ciencia y Trabajo', ESTILO_CENTRADO))
    story.append(Spacer(1, 30))
    story.append(Paragraph('P. C.I.D. Marco Antonio Toledano', ESTILO_CENTRADO))
    story.append(Paragraph('_' * 60, ESTILO_CENTRADO))
    story.append(Paragraph('Biblioteca de Área Dr. Rafael López Castañares', ESTILO_CENTRADO))
    story.append(Paragraph('BIBLIOTECA DE ÁREA DE MEDICINA Y QUÍMICA', ESTILO_CENTRADO))
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        'DOCUMENTO CONTROLADO EN EL SITIO WEB DEL SGC, QUE SE ENCUENTRA DISPONIBLE '
        'EXCLUSIVAMENTE PARA LA UNIVERSIDAD AUTÓNOMA DEL ESTADO DE MÉXICO. PROHIBIDA '
        'SU REPRODUCCIÓN TOTAL O PARCIAL.',
        ESTILO_NOTA,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer, f'registro_material_{cuenta}.pdf'


# ──────────────────────────────────────────────────────────────
# CARTA DE AUTORIZACIÓN
# ──────────────────────────────────────────────────────────────

def _campo(label, value):
    valor = value if value else '_' * 30
    return Paragraph(f'{label} <b>{valor}</b>', ESTILO_NORMAL)


def generar_carta_pdf(alumno):
    fecha = _today_str()
    nombre = _safe(alumno.nombre)
    cuenta = _safe(alumno.numero_cuenta)
    tema = _safe(alumno.tema)
    carrera = alumno.get_carrera_display() if alumno.carrera else ''
    tel = _safe(alumno.telefono)
    correo = _safe(alumno.correo)
    domicilio = _safe(alumno.domicilio)
    director = _safe(alumno.director)

    buffer, doc = _nuevo_doc(margen=1)
    story = []

    # ── Encabezado / Página 1 ──
    _encabezado(story)
    story.append(Paragraph(f'Toluca, México; a {fecha}', ESTILO_DERECHA))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Carta de autorización para la incorporación de objetos digitales en el '
        'Repositorio Institucional de la Universidad Autónoma del Estado de México.',
        ESTILO_NEGRITA_CENTRO,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph('UNIVERSIDAD AUTÓNOMA DEL ESTADO DE MÉXICO', ESTILO_CENTRADO))
    story.append(Paragraph('P R E S E N T E', ESTILO_CENTRADO))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f'El/la/los que suscribe/n {nombre}, con fundamento en los artículos 13 '
        'fracción I, 18, 21 22, 27, 30 y demás aplicables de la Ley Federal del '
        'Derecho de Autor y su Reglamento vigentes, firmo/mamos la presente Licencia '
        'de Uso Gratuita, No Exclusiva y No remunerada para la incorporación al '
        'Repositorio Institucional de la Universidad Autónoma del Estado de México '
        'de la obra literaria (artículo, capítulo de libro, libro, tesis de posgrado, '
        f'entre otros.) que lleva por título {tema}',
        ESTILO_JUSTIFICADO,
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        'Asimismo, declaro/ramos bajo protesta de decir verdad ser el/la/los '
        'autor/a/res y/o legítimo/a/s titular/es de la obra literaria y sus '
        'derivados visuales; y que responderé/remos de la autoría/titularidad, '
        'originalidad y nivel de acceso de la obra de mérito y del ejercicio '
        'pacífico de los derechos que se licencian en este acto, manifestando que '
        'no existe ninguna otra persona física o moral a la que le pertenezcan; '
        'por lo cual libero/ramos en este acto de toda responsabilidad a la '
        'Universidad Autónoma del Estado de México, así como de cualquier demanda '
        'o reclamación que llegara a formular alguna persona física o moral que '
        'considere vulnerados sus derechos o que se suponga con derecho sobre la '
        'obra mencionada, asumiendo todas las consecuencias legales y económicas '
        'a que hubiera lugar.',
        ESTILO_JUSTIFICADO,
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        'Por lo anterior, autorizo que la Oficina de Conocimiento Abierto '
        'perteneciente a esta Máxima Casa de Estudios, realice lo propio para '
        'el almacenamiento, preservación y difusión de la obra, con fines '
        'académicos y culturales en formato de acceso abierto y sin fines de lucro '
        'en los términos siguientes:',
        ESTILO_JUSTIFICADO,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph('1. De los Derechos de Autor.', ESTILO_NEGRITA_CENTRO))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'Reconozco la importancia de protección de mi obra y el movimiento de '
        'Acceso Abierto del cual forma parte la Universidad Autónoma del Estado '
        'de México, por lo tanto conozco y acepto que mi obra esté protegida '
        'bajo una de las Licencia Creative Commons que a continuación se listan, '
        'marcando con una "X" del lado izquierdo la que será aplicable a mi obra:',
        ESTILO_JUSTIFICADO,
    ))

    # ── Página 2 – Licencias CC ──
    story.append(PageBreak())
    cc_items = [
        ('Reconocimiento (BY)',
         'El autor permite copiar, reproducir, distribuir, comunicar públicamente la obra, '
         'realizar obras derivadas y hacer uso comercial, siempre citando al autor original.'),
        ('Reconocimiento - Sin obra derivada (BY-ND)',
         'Permite uso comercial citando al autor. No permite obra derivada.'),
        ('Reconocimiento - No comercial - Sin obra derivada (BY-NC-ND)',
         'Permite difusión citando al autor. No permite obra derivada ni uso comercial.'),
        ('Reconocimiento - No comercial (BY-NC)',
         'Permite obra derivada citando al autor. No permite uso comercial.'),
        ('Reconocimiento - No comercial - Compartir igual (BY-NC-SA)',
         'Permite obra derivada bajo misma licencia, citando al autor. No permite uso comercial.'),
        ('Reconocimiento - Compartir igual (BY-SA)',
         'Permite uso comercial y obra derivada con misma licencia, citando al autor.'),
    ]
    filas = [['', 'Licencia']]
    for name, desc in cc_items:
        filas.append(['☐', Paragraph(f'<b>{name}</b>: {desc}', ESTILO_NORMAL)])
    tbl = Table(filas, colWidths=[0.4 * inch, 5.6 * inch])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f9d5a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.75, colors.HexColor('#cccccc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 10))
    story.append(Paragraph('2. De la Difusión del producto', ESTILO_NEGRITA_CENTRO))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'El nivel de acceso en mi obra definirá la parcialidad o totalidad de '
        'acceso a los datos y documento a texto completo para su visibilidad '
        'en el Repositorio Institucional, por lo que la aplicable a mi obra, '
        'es el señalada del lado izquierdo en esta sección:',
        ESTILO_JUSTIFICADO,
    ))

    # ── Página 3 – Nivel de acceso ──
    story.append(PageBreak())
    access_items = [
        ('a. Abierto',
         'Permite que los metadatos y el documento a texto completo sean visualizados '
         'y descargados por cualquier usuario de manera libre y sin costo.'),
        ('b. Restringido',
         'El documento no se muestra al público. Los metadatos son visibles '
         'a petición del depositante. Se notifica al autor si alguien solicita acceso.'),
        ('c. Embargado',
         'Oculta el documento por un periodo definido. Al vencer el embargo '
         'el acceso cambia automáticamente a "acceso abierto".'),
        ('d. Cerrado',
         'El depósito no aparece en búsquedas. El documento y los metadatos '
         'NO son visibles para los usuarios.'),
    ]
    filas2 = [['', 'Nivel de acceso']]
    for name, desc in access_items:
        filas2.append(['☐', Paragraph(f'<b>{name}</b>: {desc}', ESTILO_NORMAL)])
    tbl2 = Table(filas2, colWidths=[0.4 * inch, 5.6 * inch])
    tbl2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f9d5a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.75, colors.HexColor('#cccccc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl2)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Así mismo, conozco y acepto los términos del aviso de privacidad de la '
        'UAEMex, mismo que puede ser consultado en '
        'http://web.uaemex.mx/avisos/Aviso_Privacidad.pdf; en este mismo acto '
        'otorgo mi consentimiento, para que la Universidad Autónoma del Estado de '
        'México, haga públicos mis datos personales referentes a nombres, espacio '
        'académico, opiniones y/o conclusiones vertidas en el presente trabajo.',
        ESTILO_JUSTIFICADO,
    ))

    # ── Página 4 – Firma ──
    story.append(PageBreak())
    story.append(Paragraph(
        'En pos a la protección de datos personales de terceros, y en cumplimiento '
        'a la Ley de Protección de Datos Personales en Posesión de Sujetos '
        'Obligados, estoy de acuerdo para que la tesis de mi autoría no contenga '
        'documentos donde se visualicen datos personales sensibles que puedan '
        'afectar a terceros; tales documentos como voto aprobatorio, aceptación '
        'de tesis, dedicatorias, agradecimientos, mismos que, de no ocultarlos, '
        'serán visibles en el Repositorio Institucional de la Universidad Autónoma '
        'del Estado de México, haciéndome responsable de los mismos y sin previo '
        'permiso de los terceros.',
        ESTILO_JUSTIFICADO,
    ))
    story.append(Spacer(1, 20))
    story.append(Paragraph('Firmo de Conformidad y bajo protesta de decir verdad', ESTILO_CENTRADO))
    story.append(Spacer(1, 30))
    story.append(_campo('Nombre y Firma', nombre))
    story.append(Paragraph('_' * 70, ESTILO_NORMAL))
    story.append(Spacer(1, 8))
    story.append(_campo('No. De Cuenta', cuenta))
    story.append(Paragraph('_' * 70, ESTILO_NORMAL))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        'NOTA: Ésta carta, toda vez que el autor registre los campos de llenado y '
        'las firmas correspondientes, debe digitalizarse y adjuntarse en el '
        'depósito del Repositorio Institucional de la Universidad Autónoma del '
        'Estado de México; misma que no será visible para consulta.',
        ParagraphStyle('nota_b', parent=ESTILO_NOTA, fontName='Helvetica-Bold'),
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Conozco y acepto los términos de privacidad de la Universidad Autónoma '
        'del Estado de México — http://web.uaemex.mx/avisos/Aviso_Privacidad.pdf',
        ESTILO_CENTRADO,
    ))

    # ── Página 5 – Hoja de datos del autor ──
    story.append(PageBreak())
    story.append(Paragraph(f'Toluca, México a {fecha}', ESTILO_DERECHA))
    story.append(Spacer(1, 6))
    story.append(Paragraph('Hoja de datos del autor', ESTILO_NEGRITA_CENTRO))
    story.append(Spacer(1, 14))
    story.append(_campo('Nombre:', nombre))
    story.append(_campo('Número de cuenta (en caso de aplicar):', cuenta))
    story.append(_campo('Grado académico:', director))
    story.append(_campo('Programa educativo de procedencia (aplica solo en tesis):', carrera))
    story.append(_campo('Institución donde labora:', ''))
    story.append(_campo('Domicilio:', domicilio))
    story.append(_campo('Teléfono/Fax:', tel))
    story.append(_campo('Correo electrónico (preferentemente correo institucional):', correo))
    story.append(Spacer(1, 30))
    story.append(Paragraph('_' * 40, ESTILO_CENTRADO))
    story.append(Paragraph('Nombre y firma', ESTILO_CENTRADO))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Nota: para el caso de que sean más de un autor, se deberá imprimir esta '
        'última hoja de "datos del autor" en relación al número de autores.',
        ESTILO_NOTA,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph('Esta información es recabada con fines administrativos', ESTILO_NORMAL))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Conozco y acepto los términos de privacidad de la Universidad Autónoma '
        'del Estado de México — http://web.uaemex.mx/avisos/Aviso_Privacidad.pdf',
        ESTILO_CENTRADO,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer, f'carta_autorizacion_{cuenta}.pdf'
