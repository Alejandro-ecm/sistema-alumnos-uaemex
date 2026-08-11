from django.utils import timezone
from pymarc import Field, Indicators, Leader, Record, Subfield
from pymarc.marcxml import record_to_xml

# Código MARC de organización aún no tramitado ante Library of Congress.
# Placeholder centralizado: reemplazar aquí el día que se asigne uno oficial.
ORGANIZACION = 'MX-UAEMex'

IDIOMAS_MARC = {
    'español': 'spa', 'espanol': 'spa',
    'inglés': 'eng', 'ingles': 'eng', 'english': 'eng',
    'francés': 'fre', 'frances': 'fre',
    'portugués': 'por', 'portugues': 'por',
    'alemán': 'ger', 'aleman': 'ger',
    'italiano': 'ita',
}

ARTICULOS_NO_FILTRABLES = ['el ', 'la ', 'los ', 'las ', 'un ', 'una ', 'the ', 'a ', 'an ']

RELATORES_AUTOR = {
    'COAUTOR': 'autor',
    'EDITOR': 'editor',
    'TRADUCTOR': 'traductor',
    'COMPILADOR': 'compilador',
}


def _codigo_idioma(idioma):
    return IDIOMAS_MARC.get((idioma or '').strip().lower(), 'und')


def _codigo_pais(lugar_publicacion):
    lugar = (lugar_publicacion or '').lower()
    if 'méxico' in lugar or 'mexico' in lugar:
        return 'mx '
    return 'xx '


def _caracteres_no_filtrables(titulo):
    t = (titulo or '').lstrip().lower()
    for articulo in ARTICULOS_NO_FILTRABLES:
        if t.startswith(articulo):
            return str(len(articulo))
    return '0'


def _campo_008(registro):
    hoy = timezone.now().strftime('%y%m%d')
    anio = f'{registro.anio_publicacion:04d}' if registro.anio_publicacion else 'uuuu'
    codigo_pais = _codigo_pais(registro.lugar_publicacion)
    codigo_idioma = _codigo_idioma(registro.idioma)
    campo = (
        f'{hoy}'      # 00-05  fecha en que se generó
        f's{anio}'    # 06-10  tipo de fecha + fecha 1
        f'    '       # 11-14  fecha 2 (no aplica, tipo de fecha único)
        f'{codigo_pais}'   # 15-17  país de publicación
        f'{"|" * 17}'      # 18-34  datos específicos de libro, sin catalogar
        f'{codigo_idioma}' # 35-37  idioma
        f' '               # 38     registro modificado: no
        f'd'               # 39     fuente de catalogación: otra
    )
    assert len(campo) == 40, f'campo 008 debe medir 40 caracteres, mide {len(campo)}'
    return campo


def _campo_245(registro, autor_principal):
    ind1 = '1' if autor_principal else '0'
    ind2 = _caracteres_no_filtrables(registro.titulo)
    subcampos = [Subfield(code='a', value=registro.titulo + (' :' if registro.subtitulo else ''))]
    if registro.subtitulo:
        subcampos.append(Subfield(code='b', value=registro.subtitulo + ' /'))
    if autor_principal:
        subcampos.append(Subfield(code='c', value=autor_principal.nombre + '.'))
    return Field(tag='245', indicators=Indicators(ind1, ind2), subfields=subcampos)


def _campo_264(registro):
    lugar = registro.lugar_publicacion or '[lugar no identificado]'
    editorial = registro.editorial.nombre if registro.editorial else '[editorial no identificada]'
    anio = str(registro.anio_publicacion) if registro.anio_publicacion else '[fecha no identificada]'
    return Field(
        tag='264',
        indicators=Indicators(' ', '1'),
        subfields=[
            Subfield(code='a', value=f'{lugar} :'),
            Subfield(code='b', value=f'{editorial},'),
            Subfield(code='c', value=f'{anio}.'),
        ],
    )


def generar_marc_xml(registro):
    """Genera un registro MARC21 (XML) a partir de un RegistroBibliografico.

    Función pura: no guarda nada en la base de datos, solo devuelve el XML.
    """
    record = Record()
    record.leader = Leader('00000nam a2200000 i 4500')

    record.add_field(Field(tag='001', data=f'UAEMEX{registro.id:08d}'))
    record.add_field(Field(tag='003', data=ORGANIZACION))
    record.add_field(Field(tag='005', data=timezone.now().strftime('%Y%m%d%H%M%S.0')))
    record.add_field(Field(tag='008', data=_campo_008(registro)))

    if registro.isbn:
        record.add_field(Field(
            tag='020', indicators=Indicators('', ''),
            subfields=[Subfield(code='a', value=registro.isbn)],
        ))

    record.add_field(Field(
        tag='040', indicators=Indicators('', ''),
        subfields=[
            Subfield(code='a', value=ORGANIZACION),
            Subfield(code='b', value='spa'),
            Subfield(code='c', value=ORGANIZACION),
        ],
    ))

    if registro.clasificacion:
        record.add_field(Field(
            tag='082', indicators=Indicators('0', '4'),
            subfields=[Subfield(code='a', value=registro.clasificacion)],
        ))

    autores_registro = registro.autorregistro_set.select_related('autor').order_by('orden')
    autor_principal_rel = next((ar for ar in autores_registro if ar.rol == 'PRINCIPAL'), None)
    autor_principal = autor_principal_rel.autor if autor_principal_rel else None

    if autor_principal:
        record.add_field(Field(
            tag='100', indicators=Indicators('1', ''),
            subfields=[Subfield(code='a', value=autor_principal.nombre)],
        ))

    record.add_field(_campo_245(registro, autor_principal))

    if registro.edicion:
        record.add_field(Field(
            tag='250', indicators=Indicators('', ''),
            subfields=[Subfield(code='a', value=registro.edicion)],
        ))

    record.add_field(_campo_264(registro))

    if registro.descripcion_fisica:
        record.add_field(Field(
            tag='300', indicators=Indicators('', ''),
            subfields=[Subfield(code='a', value=registro.descripcion_fisica)],
        ))

    if registro.notas:
        record.add_field(Field(
            tag='500', indicators=Indicators('', ''),
            subfields=[Subfield(code='a', value=registro.notas)],
        ))

    for materia in registro.materias.all():
        record.add_field(Field(
            tag='650', indicators=Indicators(' ', '4'),
            subfields=[Subfield(code='a', value=materia.nombre)],
        ))

    for ar in autores_registro:
        if ar.rol == 'PRINCIPAL':
            continue
        record.add_field(Field(
            tag='700', indicators=Indicators('1', ''),
            subfields=[
                Subfield(code='a', value=ar.autor.nombre),
                Subfield(code='e', value=RELATORES_AUTOR.get(ar.rol, ar.get_rol_display().lower())),
            ],
        ))

    return record_to_xml(record).decode('utf-8')
