import csv
import datetime
import io

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from alumnos.models import Alumno
from catalogo.models import Ejemplar, RegistroBibliografico

from .models import PLAZO_PRESTAMO_DIAS, Prestamo
from .services import alumnos_con_adeudo_count, no_adeudo, resumen_prestamos


class PrestamoTests(TestCase):
    def setUp(self):
        registro = RegistroBibliografico.objects.create(titulo='Rayuela')
        self.ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0002')
        self.alumno = Alumno.objects.create(
            nombre='ALUMNO DE PRUEBA', numero_cuenta='9998887', carrera='MEDICO', facultad='MEDICINA'
        )

    def test_prestamo_vencido_es_true_solo_mientras_esta_activo_y_paso_la_fecha(self):
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        prestamo = Prestamo.objects.create(
            ejemplar=self.ejemplar, alumno=self.alumno, fecha_vencimiento=ayer
        )
        self.assertTrue(prestamo.vencido)

        prestamo.estado = 'DEVUELTO'
        prestamo.save()
        self.assertFalse(prestamo.vencido)

    def test_prestamo_no_vencido_si_la_fecha_limite_no_ha_pasado(self):
        manana = timezone.now().date() + datetime.timedelta(days=1)
        prestamo = Prestamo.objects.create(
            ejemplar=self.ejemplar, alumno=self.alumno, fecha_vencimiento=manana
        )
        self.assertFalse(prestamo.vencido)

    def test_fecha_vencimiento_por_defecto_es_hoy_mas_el_plazo_configurado(self):
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)
        esperado = timezone.now().date() + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS)
        self.assertEqual(prestamo.fecha_vencimiento, esperado)

    def test_crear_un_prestamo_deja_el_ejemplar_en_prestado(self):
        Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, 'PRESTADO')

    def test_full_clean_rechaza_un_segundo_prestamo_sobre_un_ejemplar_ya_prestado(self):
        Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)
        segundo = Prestamo(ejemplar=self.ejemplar, alumno=self.alumno, fecha_vencimiento=_vencimiento())
        with self.assertRaises(ValidationError):
            segundo.full_clean()

    def test_save_rechaza_un_segundo_prestamo_sobre_un_ejemplar_ya_prestado(self):
        Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)
        segundo = Prestamo(ejemplar=self.ejemplar, alumno=self.alumno, fecha_vencimiento=_vencimiento())
        with self.assertRaises(ValidationError):
            segundo.save()
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, 'PRESTADO')

    def test_marcar_devuelto_transiciona_prestamo_y_libera_el_ejemplar(self):
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)
        prestamo.marcar_devuelto()
        self.assertEqual(prestamo.estado, 'DEVUELTO')
        self.assertIsNotNone(prestamo.fecha_devolucion)
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, 'DISPONIBLE')

    def test_marcar_devuelto_dos_veces_falla_la_segunda_vez(self):
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)
        prestamo.marcar_devuelto()
        with self.assertRaises(ValidationError):
            prestamo.marcar_devuelto()

    def test_marcar_perdido_transiciona_prestamo_y_marca_el_ejemplar_perdido(self):
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)
        prestamo.marcar_perdido()
        self.assertEqual(prestamo.estado, 'PERDIDO')
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, 'PERDIDO')

    def test_marcar_perdido_dos_veces_falla_la_segunda_vez(self):
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)
        prestamo.marcar_perdido()
        with self.assertRaises(ValidationError):
            prestamo.marcar_perdido()


def _vencimiento():
    return timezone.now().date() + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS)


class PrestamoAdminAccionesTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('bibliotecario_circ_test', 'biblio3@example.com', 'x')
        self.client = Client()
        self.client.force_login(self.staff)

        registro = RegistroBibliografico.objects.create(titulo='El Aleph')
        self.ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0003')
        self.alumno = Alumno.objects.create(
            nombre='ALUMNO ADMIN TEST', numero_cuenta='9998888', carrera='MEDICO', facultad='MEDICINA'
        )
        self.prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)

    def test_accion_marcar_devuelto_desde_el_admin_libera_el_ejemplar(self):
        self.client.post('/admin/circulacion/prestamo/', {
            'action': 'marcar_devuelto',
            '_selected_action': [str(self.prestamo.pk)],
        })
        self.prestamo.refresh_from_db()
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.prestamo.estado, 'DEVUELTO')
        self.assertEqual(self.ejemplar.estado, 'DISPONIBLE')

    def test_accion_marcar_perdido_desde_el_admin_marca_el_ejemplar_perdido(self):
        self.client.post('/admin/circulacion/prestamo/', {
            'action': 'marcar_perdido',
            '_selected_action': [str(self.prestamo.pk)],
        })
        self.prestamo.refresh_from_db()
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.prestamo.estado, 'PERDIDO')
        self.assertEqual(self.ejemplar.estado, 'PERDIDO')


class NoAdeudoTests(TestCase):
    def setUp(self):
        registro = RegistroBibliografico.objects.create(titulo='El Aleph')
        self.ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0004')
        self.alumno = Alumno.objects.create(
            nombre='ALUMNO NO ADEUDO TEST', numero_cuenta='9998889', carrera='MEDICO', facultad='MEDICINA'
        )

    def test_alumno_sin_prestamos_no_tiene_adeudo(self):
        resultado = no_adeudo(self.alumno)
        self.assertTrue(resultado.sin_adeudo)
        self.assertEqual(resultado.prestamos_vencidos, [])

    def test_alumno_con_prestamo_activo_no_vencido_no_tiene_adeudo(self):
        manana = timezone.now().date() + datetime.timedelta(days=1)
        Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno, fecha_vencimiento=manana)
        resultado = no_adeudo(self.alumno)
        self.assertTrue(resultado.sin_adeudo)

    def test_alumno_con_prestamo_activo_vencido_tiene_adeudo(self):
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno, fecha_vencimiento=ayer)
        resultado = no_adeudo(self.alumno)
        self.assertFalse(resultado.sin_adeudo)
        self.assertEqual(resultado.prestamos_vencidos, [prestamo])

    def test_prestamo_vencido_pero_ya_devuelto_no_cuenta_como_adeudo(self):
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno, fecha_vencimiento=ayer)
        prestamo.marcar_devuelto()
        resultado = no_adeudo(self.alumno)
        self.assertTrue(resultado.sin_adeudo)


class ResumenPrestamosTests(TestCase):
    def setUp(self):
        registro = RegistroBibliografico.objects.create(titulo='Ficciones')
        self.alumno = Alumno.objects.create(
            nombre='ALUMNO RESUMEN TEST', numero_cuenta='9998890', carrera='MEDICO', facultad='MEDICINA'
        )
        self.ej_activo = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0005')
        self.ej_vencido = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0006')
        self.ej_devuelto = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0007')

    def test_resumen_cuenta_activos_y_vencidos_excluyendo_devueltos(self):
        manana = timezone.now().date() + datetime.timedelta(days=1)
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        Prestamo.objects.create(ejemplar=self.ej_activo, alumno=self.alumno, fecha_vencimiento=manana)
        Prestamo.objects.create(ejemplar=self.ej_vencido, alumno=self.alumno, fecha_vencimiento=ayer)
        devuelto = Prestamo.objects.create(ejemplar=self.ej_devuelto, alumno=self.alumno, fecha_vencimiento=ayer)
        devuelto.marcar_devuelto()

        resultado = resumen_prestamos()
        self.assertEqual(resultado.activos, 2)
        self.assertEqual(resultado.vencidos, 1)


class AlumnosConAdeudoCountTests(TestCase):
    def test_dos_prestamos_vencidos_del_mismo_alumno_cuentan_una_sola_vez(self):
        registro = RegistroBibliografico.objects.create(titulo='El Aleph')
        alumno = Alumno.objects.create(
            nombre='ALUMNO ADEUDO COUNT TEST', numero_cuenta='9998891', carrera='MEDICO', facultad='MEDICINA'
        )
        ej1 = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0008')
        ej2 = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0009')
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        Prestamo.objects.create(ejemplar=ej1, alumno=alumno, fecha_vencimiento=ayer)
        Prestamo.objects.create(ejemplar=ej2, alumno=alumno, fecha_vencimiento=ayer)

        self.assertEqual(alumnos_con_adeudo_count(), 1)


class PrestamoCsvExportTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('bibliotecario_csv_test', 'biblio4@example.com', 'x')
        self.client = Client()
        self.client.force_login(self.staff)

        registro = RegistroBibliografico.objects.create(titulo='Rayuela')
        self.ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0010')
        self.alumno = Alumno.objects.create(
            nombre='ALUMNO CSV PRESTAMO', numero_cuenta='9998892', carrera='MEDICO', facultad='MEDICINA'
        )
        self.prestamo = Prestamo.objects.create(ejemplar=self.ejemplar, alumno=self.alumno)

    def test_exportar_csv_prestamos_genera_csv_con_datos_correctos(self):
        response = self.client.post('/admin/circulacion/prestamo/', {
            'action': 'exportar_prestamos_csv',
            '_selected_action': [str(self.prestamo.pk)],
        })
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('prestamos.csv', response['Content-Disposition'])
        filas = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        self.assertEqual(filas[0][0], 'Código de barras')
        self.assertEqual(filas[1][0], 'EJ-0010')
        self.assertEqual(filas[1][2], '9998892')
