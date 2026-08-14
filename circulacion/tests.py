import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from alumnos.models import Alumno
from catalogo.models import Ejemplar, RegistroBibliografico

from .models import PLAZO_PRESTAMO_DIAS, TARIFA_MULTA_DIA, Prestamo
from .services import (
    alumnos_con_adeudo_count, crear_prestamo, multas_por_libro, multas_recientes, no_adeudo, resumen_multas,
    resumen_prestamos,
)


class PrestamoTests(TestCase):
    def setUp(self):
        registro = RegistroBibliografico.objects.create(titulo='Rayuela')
        self.ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0002')
        self.alumno = Alumno.objects.create(
            nombre='ALUMNO DE PRUEBA', numero_cuenta='9998887', carrera='MEDICO', facultad='MEDICINA'
        )

    def _crear(self, ejemplar=None, fecha_devolucion=None):
        return crear_prestamo(
            alumno_nombre=self.alumno.nombre, matricula=self.alumno.numero_cuenta,
            fecha_devolucion=fecha_devolucion, ejemplar_ids=[(ejemplar or self.ejemplar).pk],
        )

    def test_prestamo_vencido_es_true_solo_mientras_esta_activo_y_paso_la_fecha(self):
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        prestamo = self._crear(fecha_devolucion=ayer)
        self.assertTrue(prestamo.vencido)

        prestamo.estado = 'DEVUELTO'
        prestamo.save()
        self.assertFalse(prestamo.vencido)

    def test_prestamo_no_vencido_si_la_fecha_limite_no_ha_pasado(self):
        manana = timezone.now().date() + datetime.timedelta(days=1)
        prestamo = self._crear(fecha_devolucion=manana)
        self.assertFalse(prestamo.vencido)

    def test_fecha_devolucion_por_defecto_es_hoy_mas_el_plazo_configurado(self):
        prestamo = self._crear()
        esperado = timezone.now().date() + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS)
        self.assertEqual(prestamo.fecha_devolucion, esperado)

    def test_crear_un_prestamo_deja_el_ejemplar_en_prestado(self):
        self._crear()
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, 'PRESTADO')

    def test_crear_prestamo_sin_libros_falla(self):
        with self.assertRaises(ValidationError):
            crear_prestamo(alumno_nombre=self.alumno.nombre, matricula=self.alumno.numero_cuenta, ejemplar_ids=[])

    def test_crear_prestamo_sobre_un_ejemplar_ya_prestado_falla(self):
        self._crear()
        with self.assertRaises(ValidationError):
            self._crear()
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, 'PRESTADO')

    def test_marcar_devuelto_transiciona_prestamo_y_libera_el_ejemplar(self):
        prestamo = self._crear()
        prestamo.marcar_devuelto()
        self.assertEqual(prestamo.estado, 'DEVUELTO')
        self.assertIsNotNone(prestamo.fecha_devolucion_real)
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, 'DISPONIBLE')

    def test_marcar_devuelto_dos_veces_falla_la_segunda_vez(self):
        prestamo = self._crear()
        prestamo.marcar_devuelto()
        with self.assertRaises(ValidationError):
            prestamo.marcar_devuelto()

    def test_marcar_perdido_transiciona_prestamo_y_marca_el_ejemplar_perdido(self):
        prestamo = self._crear()
        prestamo.marcar_perdido()
        self.assertEqual(prestamo.estado, 'PERDIDO')
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.ejemplar.estado, 'PERDIDO')

    def test_marcar_perdido_dos_veces_falla_la_segunda_vez(self):
        prestamo = self._crear()
        prestamo.marcar_perdido()
        with self.assertRaises(ValidationError):
            prestamo.marcar_perdido()

    def test_marcar_devuelto_sin_atraso_no_genera_multa(self):
        prestamo = self._crear()
        prestamo.marcar_devuelto()
        self.assertEqual(prestamo.dias_retraso, 0)
        self.assertEqual(prestamo.multa_total, 0)

    def test_marcar_devuelto_con_atraso_calcula_dias_retraso_y_multa_total(self):
        hace_tres_dias = timezone.now().date() - datetime.timedelta(days=3)
        prestamo = self._crear(fecha_devolucion=hace_tres_dias)
        prestamo.marcar_devuelto()
        self.assertEqual(prestamo.dias_retraso, 3)
        self.assertEqual(prestamo.multa_total, 3 * TARIFA_MULTA_DIA)

    def test_marcar_devuelto_persiste_descuento_cobro_y_pago(self):
        hace_dos_dias = timezone.now().date() - datetime.timedelta(days=2)
        prestamo = self._crear(fecha_devolucion=hace_dos_dias)
        prestamo.marcar_devuelto(multa_descuento=10, multa_cobrada=30, multa_pagada=True)
        self.assertEqual(prestamo.multa_descuento, 10)
        self.assertEqual(prestamo.multa_cobrada, 30)
        self.assertTrue(prestamo.multa_pagada)
        self.assertIsNotNone(prestamo.multa_pagada_at)


class CrearPrestamoAdminViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('bibliotecario_crear_test', 'biblio_crear@example.com', 'x')
        self.client = Client()
        self.client.force_login(self.staff)

        registro = RegistroBibliografico.objects.create(titulo='Cien años de soledad')
        self.ej1 = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0100')
        self.ej2 = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0101')

    def test_crear_prestamo_agrupa_varios_libros_bajo_un_folio(self):
        hoy = timezone.localdate()
        response = self.client.post('/admin/circulacion/prestamo/crear/', {
            'alumno_nombre': 'Alumno de Mostrador',
            'matricula': '',
            'telefono': '',
            'carrera': '',
            'fecha_salida': hoy.isoformat(),
            'fecha_devolucion': (hoy + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS)).isoformat(),
            'observaciones': '',
            'ejemplares': f'{self.ej1.pk},{self.ej2.pk}',
        })
        self.assertRedirects(response, '/admin/circulacion/prestamo/')
        prestamo = Prestamo.objects.get()
        self.assertTrue(prestamo.folio.startswith('PREST-'))
        self.assertEqual(prestamo.libros.count(), 2)
        self.ej1.refresh_from_db()
        self.ej2.refresh_from_db()
        self.assertEqual(self.ej1.estado, 'PRESTADO')
        self.assertEqual(self.ej2.estado, 'PRESTADO')

    def test_crear_prestamo_sin_libros_no_crea_nada_y_muestra_error(self):
        hoy = timezone.localdate()
        response = self.client.post('/admin/circulacion/prestamo/crear/', {
            'alumno_nombre': 'Alumno de Mostrador',
            'fecha_salida': hoy.isoformat(),
            'fecha_devolucion': (hoy + datetime.timedelta(days=PLAZO_PRESTAMO_DIAS)).isoformat(),
            'ejemplares': '',
        })
        self.assertRedirects(response, '/admin/circulacion/prestamo/')
        self.assertEqual(Prestamo.objects.count(), 0)


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
        self.prestamo = crear_prestamo(
            alumno_nombre=self.alumno.nombre, matricula=self.alumno.numero_cuenta, ejemplar_ids=[self.ejemplar.pk]
        )

    def test_vista_registrar_devolucion_libera_el_ejemplar(self):
        self.client.post(f'/admin/circulacion/prestamo/{self.prestamo.pk}/devolver/', {
            'multa_descuento': '0',
            'multa_cobrada': '0',
        })
        self.prestamo.refresh_from_db()
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.prestamo.estado, 'DEVUELTO')
        self.assertEqual(self.ejemplar.estado, 'DISPONIBLE')

    def test_marcar_perdido_desde_el_admin_marca_el_ejemplar_perdido(self):
        self.client.post(f'/admin/circulacion/prestamo/{self.prestamo.pk}/perdido/')
        self.prestamo.refresh_from_db()
        self.ejemplar.refresh_from_db()
        self.assertEqual(self.prestamo.estado, 'PERDIDO')
        self.assertEqual(self.ejemplar.estado, 'PERDIDO')


class RegistrarDevolucionViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser('bibliotecario_devol_test', 'biblio5@example.com', 'x')
        self.client = Client()
        self.client.force_login(self.staff)

        registro = RegistroBibliografico.objects.create(titulo='Ficciones')
        self.ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0011')
        self.alumno = Alumno.objects.create(
            nombre='ALUMNO DEVOL TEST', numero_cuenta='9998893', carrera='MEDICO', facultad='MEDICINA'
        )
        hace_cuatro_dias = timezone.now().date() - datetime.timedelta(days=4)
        self.prestamo = crear_prestamo(
            alumno_nombre=self.alumno.nombre, matricula=self.alumno.numero_cuenta,
            fecha_devolucion=hace_cuatro_dias, ejemplar_ids=[self.ejemplar.pk],
        )
        self.url = f'/admin/circulacion/prestamo/{self.prestamo.pk}/devolver/'

    def test_get_muestra_la_multa_estimada(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(4 * TARIFA_MULTA_DIA))

    def test_post_invalido_no_cambia_el_prestamo(self):
        response = self.client.post(self.url, {'multa_descuento': 'no-es-un-numero', 'multa_cobrada': '0'})
        self.assertEqual(response.status_code, 200)
        self.prestamo.refresh_from_db()
        self.assertEqual(self.prestamo.estado, 'ACTIVO')

    def test_post_valido_marca_devuelto_y_redirige(self):
        response = self.client.post(self.url, {
            'multa_descuento': '0', 'multa_cobrada': str(4 * TARIFA_MULTA_DIA), 'multa_pagada': 'on',
        })
        self.assertRedirects(response, '/admin/circulacion/prestamo/')
        self.prestamo.refresh_from_db()
        self.assertEqual(self.prestamo.estado, 'DEVUELTO')
        self.assertEqual(self.prestamo.multa_cobrada, 4 * TARIFA_MULTA_DIA)
        self.assertTrue(self.prestamo.multa_pagada)

    def test_sin_permiso_change_prestamo_recibe_403(self):
        sin_permiso = User.objects.create_user('sin_permiso_test', 'sinpermiso@example.com', 'x', is_staff=True)
        client = Client()
        client.force_login(sin_permiso)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 403)


class NoAdeudoTests(TestCase):
    def setUp(self):
        registro = RegistroBibliografico.objects.create(titulo='El Aleph')
        self.ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0004')
        self.alumno = Alumno.objects.create(
            nombre='ALUMNO NO ADEUDO TEST', numero_cuenta='9998889', carrera='MEDICO', facultad='MEDICINA'
        )

    def _crear(self, fecha_devolucion=None):
        return crear_prestamo(
            alumno_nombre=self.alumno.nombre, matricula=self.alumno.numero_cuenta,
            fecha_devolucion=fecha_devolucion, ejemplar_ids=[self.ejemplar.pk],
        )

    def test_alumno_sin_prestamos_no_tiene_adeudo(self):
        resultado = no_adeudo(self.alumno)
        self.assertTrue(resultado.sin_adeudo)
        self.assertEqual(resultado.prestamos_vencidos, [])

    def test_alumno_con_prestamo_activo_no_vencido_no_tiene_adeudo(self):
        manana = timezone.now().date() + datetime.timedelta(days=1)
        self._crear(fecha_devolucion=manana)
        resultado = no_adeudo(self.alumno)
        self.assertTrue(resultado.sin_adeudo)

    def test_alumno_con_prestamo_activo_vencido_tiene_adeudo(self):
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        prestamo = self._crear(fecha_devolucion=ayer)
        resultado = no_adeudo(self.alumno)
        self.assertFalse(resultado.sin_adeudo)
        self.assertEqual(resultado.prestamos_vencidos, [prestamo])

    def test_prestamo_vencido_pero_ya_devuelto_no_cuenta_como_adeudo(self):
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        prestamo = self._crear(fecha_devolucion=ayer)
        prestamo.marcar_devuelto()
        resultado = no_adeudo(self.alumno)
        self.assertTrue(resultado.sin_adeudo)


class ResumenPrestamosTests(TestCase):
    def setUp(self):
        registro = RegistroBibliografico.objects.create(titulo='Ficciones')
        self.ej_activo = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0005')
        self.ej_vencido = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0006')
        self.ej_devuelto = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0007')

    def _crear(self, ejemplar, fecha_devolucion):
        return crear_prestamo(
            alumno_nombre='Alumno de Prueba', fecha_devolucion=fecha_devolucion, ejemplar_ids=[ejemplar.pk]
        )

    def test_resumen_cuenta_activos_y_vencidos_excluyendo_devueltos(self):
        manana = timezone.now().date() + datetime.timedelta(days=1)
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        self._crear(self.ej_activo, manana)
        self._crear(self.ej_vencido, ayer)
        devuelto = self._crear(self.ej_devuelto, ayer)
        devuelto.marcar_devuelto()

        resultado = resumen_prestamos()
        self.assertEqual(resultado.activos, 2)
        self.assertEqual(resultado.vencidos, 1)

    def test_resumen_cuenta_devueltos_y_total(self):
        manana = timezone.now().date() + datetime.timedelta(days=1)
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        self._crear(self.ej_activo, manana)
        self._crear(self.ej_vencido, ayer)
        devuelto = self._crear(self.ej_devuelto, ayer)
        devuelto.marcar_devuelto()

        resultado = resumen_prestamos()
        self.assertEqual(resultado.devueltos, 1)
        self.assertEqual(resultado.total, 3)


class ResumenMultasTests(TestCase):
    def setUp(self):
        registro = RegistroBibliografico.objects.create(titulo='Ficciones')
        self.ej_pagada = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0012')
        self.ej_pendiente = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0013')
        self.ej_sin_atraso = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0014')

    def _crear(self, ejemplar, fecha_devolucion):
        return crear_prestamo(
            alumno_nombre='Alumno de Prueba', fecha_devolucion=fecha_devolucion, ejemplar_ids=[ejemplar.pk]
        )

    def test_resumen_multas_con_datos_mixtos(self):
        hace_dos_dias = timezone.now().date() - datetime.timedelta(days=2)
        hace_un_dia = timezone.now().date() - datetime.timedelta(days=1)
        manana = timezone.now().date() + datetime.timedelta(days=1)

        pagada = self._crear(self.ej_pagada, hace_dos_dias)
        pagada.marcar_devuelto(multa_descuento=5, multa_cobrada=35, multa_pagada=True)

        pendiente = self._crear(self.ej_pendiente, hace_un_dia)
        pendiente.marcar_devuelto()

        self._crear(self.ej_sin_atraso, manana)

        resultado = resumen_multas()
        self.assertEqual(resultado.con_multa, 2)
        self.assertEqual(resultado.total_generado, 2 * TARIFA_MULTA_DIA + 1 * TARIFA_MULTA_DIA)
        self.assertEqual(resultado.total_cobrado, 35)
        self.assertEqual(resultado.total_descuentos, 5)
        self.assertEqual(resultado.pendientes, 1)


class MultasPorLibroYRecientesTests(TestCase):
    def setUp(self):
        self.registro_a = RegistroBibliografico.objects.create(titulo='Ficciones')
        self.registro_b = RegistroBibliografico.objects.create(titulo='El Aleph')
        self.ej_a1 = Ejemplar.objects.create(registro=self.registro_a, codigo_barras='EJ-0015')
        self.ej_a2 = Ejemplar.objects.create(registro=self.registro_a, codigo_barras='EJ-0016')
        self.ej_b1 = Ejemplar.objects.create(registro=self.registro_b, codigo_barras='EJ-0017')
        self.ej_sin_atraso = Ejemplar.objects.create(registro=self.registro_b, codigo_barras='EJ-0018')

    def _crear(self, ejemplar, fecha_devolucion):
        return crear_prestamo(
            alumno_nombre='Alumno de Prueba', fecha_devolucion=fecha_devolucion, ejemplar_ids=[ejemplar.pk]
        )

    def test_multas_por_libro_agrupa_y_suma_por_registro(self):
        hace_dos_dias = timezone.now().date() - datetime.timedelta(days=2)
        hace_un_dia = timezone.now().date() - datetime.timedelta(days=1)
        manana = timezone.now().date() + datetime.timedelta(days=1)

        p1 = self._crear(self.ej_a1, hace_dos_dias)
        p1.marcar_devuelto()
        p2 = self._crear(self.ej_a2, hace_un_dia)
        p2.marcar_devuelto()
        p3 = self._crear(self.ej_b1, hace_un_dia)
        p3.marcar_devuelto()
        self._crear(self.ej_sin_atraso, manana)

        por_libro = {item['ejemplar__registro__titulo']: item for item in multas_por_libro()}
        self.assertEqual(por_libro['Ficciones']['veces'], 2)
        self.assertEqual(por_libro['Ficciones']['total_multas'], 3 * TARIFA_MULTA_DIA)
        self.assertEqual(por_libro['El Aleph']['veces'], 1)
        self.assertEqual(por_libro['El Aleph']['total_multas'], 1 * TARIFA_MULTA_DIA)

    def test_multas_recientes_excluye_prestamos_sin_multa_y_ordena_por_fecha_devolucion(self):
        hace_un_dia = timezone.now().date() - datetime.timedelta(days=1)
        manana = timezone.now().date() + datetime.timedelta(days=1)

        con_multa = self._crear(self.ej_a1, hace_un_dia)
        con_multa.marcar_devuelto()
        self._crear(self.ej_sin_atraso, manana)

        recientes = list(multas_recientes())
        self.assertEqual(len(recientes), 1)
        self.assertEqual(recientes[0].pk, con_multa.pk)


class AlumnosConAdeudoCountTests(TestCase):
    def test_dos_prestamos_vencidos_del_mismo_alumno_cuentan_una_sola_vez(self):
        registro = RegistroBibliografico.objects.create(titulo='El Aleph')
        alumno = Alumno.objects.create(
            nombre='ALUMNO ADEUDO COUNT TEST', numero_cuenta='9998891', carrera='MEDICO', facultad='MEDICINA'
        )
        ej1 = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0008')
        ej2 = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-0009')
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        crear_prestamo(
            alumno_nombre=alumno.nombre, matricula=alumno.numero_cuenta,
            fecha_devolucion=ayer, ejemplar_ids=[ej1.pk],
        )
        crear_prestamo(
            alumno_nombre=alumno.nombre, matricula=alumno.numero_cuenta,
            fecha_devolucion=ayer, ejemplar_ids=[ej2.pk],
        )

        self.assertEqual(alumnos_con_adeudo_count(), 1)
