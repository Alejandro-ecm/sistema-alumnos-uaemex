import csv
import datetime
import io

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from pymarc.marcxml import parse_xml_to_array

from alumnos.models import Alumno
from circulacion.models import Prestamo

from .marc import _campo_008, generar_marc_xml
from .models import Autor, AutorRegistro, Editorial, Ejemplar, Materia, RegistroBibliografico


class RegistroBibliograficoTests(TestCase):
    def setUp(self):
        self.autor = Autor.objects.create(nombre='Gabriel García Márquez')
        self.editorial = Editorial.objects.create(nombre='Sudamericana')
        self.materia = Materia.objects.create(nombre='Literatura latinoamericana')
        self.registro = RegistroBibliografico.objects.create(
            titulo='Cien años de soledad',
            editorial=self.editorial,
            clasificacion='863 G216c',
        )
        self.registro.materias.add(self.materia)
        AutorRegistro.objects.create(registro=self.registro, autor=self.autor, rol='PRINCIPAL')

    def test_registro_expone_autor_por_relacion_m2m(self):
        self.assertIn(self.autor, self.registro.autores.all())

    def test_registro_expone_materia(self):
        self.assertIn(self.materia, self.registro.materias.all())

    def test_no_se_puede_repetir_el_mismo_autor_dos_veces_en_un_registro(self):
        with self.assertRaises(Exception):
            AutorRegistro.objects.create(registro=self.registro, autor=self.autor, rol='COAUTOR')

    def test_ejemplar_queda_asociado_a_su_registro(self):
        ejemplar = Ejemplar.objects.create(registro=self.registro, codigo_barras='EJ-0001')
        self.assertIn(ejemplar, self.registro.ejemplares.all())
        self.assertEqual(ejemplar.estado, 'DISPONIBLE')


class MarcXmlTests(TestCase):
    def setUp(self):
        self.autor_principal = Autor.objects.create(nombre='García Márquez, Gabriel')
        self.coautor = Autor.objects.create(nombre='Vargas Llosa, Mario')
        self.editorial = Editorial.objects.create(nombre='Sudamericana')
        self.materia = Materia.objects.create(nombre='Literatura latinoamericana')
        self.registro = RegistroBibliografico.objects.create(
            titulo='Cien años de soledad',
            subtitulo='novela',
            isbn='978-0307474728',
            edicion='1a ed.',
            anio_publicacion=1967,
            lugar_publicacion='Buenos Aires, México',
            idioma='Español',
            descripcion_fisica='471 p. ; 21 cm.',
            clasificacion='863 G216c',
            notas='Incluye índice.',
            editorial=self.editorial,
        )
        self.registro.materias.add(self.materia)
        AutorRegistro.objects.create(registro=self.registro, autor=self.autor_principal, rol='PRINCIPAL', orden=1)
        AutorRegistro.objects.create(registro=self.registro, autor=self.coautor, rol='COAUTOR', orden=2)

    def test_campo_008_siempre_mide_40_caracteres(self):
        self.assertEqual(len(_campo_008(self.registro)), 40)

    def test_campo_008_mide_40_caracteres_con_datos_vacios(self):
        registro_vacio = RegistroBibliografico.objects.create(titulo='Sin datos')
        self.assertEqual(len(_campo_008(registro_vacio)), 40)

    def test_generar_marc_xml_de_registro_completo_es_legible_por_pymarc(self):
        xml = generar_marc_xml(self.registro)
        registros = parse_xml_to_array(io.BytesIO(xml.encode('utf-8')))

        self.assertEqual(len(registros), 1)
        record = registros[0]
        self.assertEqual(record['245']['a'], 'Cien años de soledad :')
        self.assertEqual(record['020']['a'], self.registro.isbn)

    def test_registro_con_solo_titulo_genera_xml_valido_sin_excepciones(self):
        registro_minimo = RegistroBibliografico.objects.create(titulo='Título mínimo')

        xml = generar_marc_xml(registro_minimo)
        registros = parse_xml_to_array(io.BytesIO(xml.encode('utf-8')))

        self.assertEqual(len(registros), 1)
        record = registros[0]
        self.assertEqual(record['245']['a'], 'Título mínimo')
        self.assertEqual(record.get_fields('020'), [])
        self.assertEqual(record.get_fields('082'), [])
        self.assertEqual(record.get_fields('250'), [])
        self.assertEqual(record.get_fields('300'), [])
        self.assertEqual(record.get_fields('500'), [])
        self.assertIn('[lugar no identificado]', record['264']['a'])
        self.assertIn('[editorial no identificada]', record['264']['b'])
        self.assertIn('[fecha no identificada]', record['264']['c'])

    def test_dos_autores_producen_exactamente_un_100_y_un_700_con_relator_correcto(self):
        xml = generar_marc_xml(self.registro)
        record = parse_xml_to_array(io.BytesIO(xml.encode('utf-8')))[0]

        campos_100 = record.get_fields('100')
        campos_700 = record.get_fields('700')

        self.assertEqual(len(campos_100), 1)
        self.assertEqual(campos_100[0]['a'], self.autor_principal.nombre)

        self.assertEqual(len(campos_700), 1)
        self.assertEqual(campos_700[0]['a'], self.coautor.nombre)
        self.assertEqual(campos_700[0]['e'], 'autor')


class BusquedaAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('bibliotecario_test', 'biblio@example.com', 'x')
        self.client = Client()
        self.client.force_login(self.staff)

        autor = Autor.objects.create(nombre='Borges, Jorge Luis')
        editorial = Editorial.objects.create(nombre='Emecé')
        self.registro = RegistroBibliografico.objects.create(titulo='Ficciones', editorial=editorial)
        AutorRegistro.objects.create(registro=self.registro, autor=autor, rol='PRINCIPAL')

    def test_busqueda_por_nombre_de_autor_encuentra_el_registro(self):
        resp = self.client.get('/admin/catalogo/registrobibliografico/', {'q': 'Borges'})
        self.assertContains(resp, 'Ficciones')

    def test_busqueda_por_nombre_de_editorial_encuentra_el_registro(self):
        resp = self.client.get('/admin/catalogo/registrobibliografico/', {'q': 'Emecé'})
        self.assertContains(resp, 'Ficciones')

    def test_busqueda_sin_coincidencias_no_devuelve_el_registro(self):
        resp = self.client.get('/admin/catalogo/registrobibliografico/', {'q': 'inexistente_xyz'})
        self.assertNotContains(resp, 'Ficciones')


class EjemplarTests(TestCase):
    def setUp(self):
        self.registro = RegistroBibliografico.objects.create(titulo='Rayuela')

    def test_no_se_puede_repetir_el_mismo_codigo_de_barras_en_dos_ejemplares(self):
        Ejemplar.objects.create(registro=self.registro, codigo_barras='EJ-9000')
        with self.assertRaises(Exception):
            Ejemplar.objects.create(registro=self.registro, codigo_barras='EJ-9000')

    def test_ejemplar_se_puede_crear_desde_el_alta_inline_del_registro(self):
        staff = User.objects.create_superuser('bibliotecario_inline_test', 'biblio2@example.com', 'x')
        client = Client()
        client.force_login(staff)

        resp = client.get(f'/admin/catalogo/registrobibliografico/{self.registro.id}/change/')
        self.assertContains(resp, 'id_ejemplares-0-codigo_barras')


class PanelBibliotecaTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('bibliotecario_panel_test', 'biblio5@example.com', 'x')
        self.client = Client()
        self.client.force_login(self.staff)

        registro = RegistroBibliografico.objects.create(titulo='Pedro Páramo')
        self.ej_disponible = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0011')
        self.ej_prestado = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0012')
        alumno = Alumno.objects.create(
            nombre='ALUMNO PANEL TEST', numero_cuenta='9998893', carrera='MEDICO', facultad='MEDICINA'
        )
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        Prestamo.objects.create(ejemplar=self.ej_prestado, alumno=alumno, fecha_vencimiento=ayer)

    def test_panel_biblioteca_muestra_las_estadisticas_esperadas(self):
        response = self.client.get(reverse('admin:catalogo_panel_biblioteca'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_ejemplares'], 2)
        self.assertEqual(response.context['ejemplares_disponibles'], 1)
        self.assertEqual(response.context['prestamos_activos'], 1)
        self.assertEqual(response.context['prestamos_vencidos'], 1)


class EjemplarCsvExportTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('bibliotecario_csv_ej_test', 'biblio6@example.com', 'x')
        self.client = Client()
        self.client.force_login(self.staff)

        registro = RegistroBibliografico.objects.create(titulo='Ficciones')
        self.ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0013', ubicacion='A-1')

    def test_exportar_csv_ejemplares_genera_csv_con_datos_correctos(self):
        response = self.client.post('/admin/catalogo/ejemplar/', {
            'action': 'exportar_ejemplares_csv',
            '_selected_action': [str(self.ejemplar.pk)],
        })
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('ejemplares.csv', response['Content-Disposition'])
        filas = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        self.assertEqual(filas[0][0], 'Código de barras')
        self.assertEqual(filas[1][0], 'EJ-0013')
        self.assertEqual(filas[1][2], 'A-1')
