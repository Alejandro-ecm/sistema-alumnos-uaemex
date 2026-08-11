from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Alumno, ImpresionConstancia

User = get_user_model()


def _crear_alumno(**overrides):
    datos = dict(
        nombre='ALUMNO DE PRUEBA',
        numero_cuenta='1234567',
        carrera='MEDICO',
        facultad='MEDICINA',
    )
    datos.update(overrides)
    return Alumno.objects.create(**datos)


# ──────────────────────────────────────────────────────────────
# AUTENTICACIÓN
# ──────────────────────────────────────────────────────────────

class AutenticacionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff1', password='clave-segura-123', is_staff=True
        )

    def test_login_usuario_valido(self):
        self.assertTrue(self.client.login(username='staff1', password='clave-segura-123'))

    def test_login_usuario_password_invalida(self):
        self.assertFalse(self.client.login(username='staff1', password='password-incorrecta'))

    def test_usuario_no_autenticado_es_redirigido_al_login_del_panel(self):
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)


# ──────────────────────────────────────────────────────────────
# PERMISOS POR ROL
# ──────────────────────────────────────────────────────────────

class PermisosTests(TestCase):
    def setUp(self):
        self.admvo = User.objects.create_user(
            username='admvo1', password='clave-segura-123', is_staff=True
        )
        self.admvo.groups.add(Group.objects.get(name='Administrativos'))

        self.mant = User.objects.create_user(
            username='mant1', password='clave-segura-123', is_staff=True
        )
        self.mant.groups.add(Group.objects.get(name='Mantenimiento'))

        self.sin_grupo = User.objects.create_user(
            username='staffsin', password='clave-segura-123', is_staff=True
        )

    def test_administrativo_accede_al_listado_de_alumnos(self):
        self.client.login(username='admvo1', password='clave-segura-123')
        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_mantenimiento_accede_a_su_panel(self):
        self.client.login(username='mant1', password='clave-segura-123')
        response = self.client.get(reverse('admin:deteccion_libros_panel_mantenimiento'))
        self.assertEqual(response.status_code, 200)

    def test_administrativo_no_accede_a_vista_de_seguridad(self):
        self.client.login(username='admvo1', password='clave-segura-123')
        response = self.client.get(reverse('admin:deteccion_libros_vista_seguridad'))
        self.assertEqual(response.status_code, 403)

    def test_mantenimiento_no_accede_al_listado_de_alumnos(self):
        self.client.login(username='mant1', password='clave-segura-123')
        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertEqual(response.status_code, 403)

    def test_staff_sin_grupo_no_accede_a_panel_mantenimiento(self):
        self.client.login(username='staffsin', password='clave-segura-123')
        response = self.client.get(reverse('admin:deteccion_libros_panel_mantenimiento'))
        self.assertEqual(response.status_code, 403)


# ──────────────────────────────────────────────────────────────
# DOCUMENTOS (autorización real en backend)
# ──────────────────────────────────────────────────────────────

class DocumentosTests(TestCase):
    def setUp(self):
        self.alumno = _crear_alumno()
        self.admvo = User.objects.create_user(
            username='admvo2', password='clave-segura-123', is_staff=True
        )
        self.admvo.groups.add(Group.objects.get(name='Administrativos'))

    def test_navegador_anonimo_no_autorizado_no_accede_a_documentos_ajenos(self):
        response = self.client.get(reverse('carta', args=[self.alumno.id]))
        self.assertEqual(response.status_code, 403)

    def test_flujo_registro_autoriza_sus_propios_documentos(self):
        datos = {
            'nombre': 'NUEVO ALUMNO',
            'numero_cuenta': '1112223',
            'carrera': 'MEDICO',
            'acepta_terminos': 'on',
        }
        response = self.client.post(reverse('registro_medicina'), datos)
        self.assertEqual(response.status_code, 302)
        alumno_id = Alumno.objects.get(numero_cuenta='1112223').id

        response = self.client.get(reverse('carta', args=[alumno_id]))
        self.assertEqual(response.status_code, 200)

    def test_sesion_de_un_alumno_no_autoriza_documentos_de_otro(self):
        datos = {
            'nombre': 'TERCER ALUMNO',
            'numero_cuenta': '3334445',
            'carrera': 'MEDICO',
            'acepta_terminos': 'on',
        }
        self.client.post(reverse('registro_medicina'), datos)
        # la sesión quedó autorizada solo para "TERCER ALUMNO", no para self.alumno
        response = self.client.get(reverse('carta', args=[self.alumno.id]))
        self.assertEqual(response.status_code, 403)

    def test_administrativo_puede_generar_documentos_de_cualquier_alumno(self):
        self.client.login(username='admvo2', password='clave-segura-123')
        self.assertEqual(self.client.get(reverse('pdf', args=[self.alumno.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('pdf2', args=[self.alumno.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('carta', args=[self.alumno.id])).status_code, 200)

    def test_generar_documento_registra_la_impresion(self):
        self.client.login(username='admvo2', password='clave-segura-123')
        self.assertEqual(ImpresionConstancia.objects.filter(alumno=self.alumno).count(), 0)
        self.client.get(reverse('pdf', args=[self.alumno.id]))
        self.assertEqual(
            ImpresionConstancia.objects.filter(alumno=self.alumno, tipo='NO_ADEUDO').count(), 1
        )

    def test_documento_de_alumno_inexistente_da_404_no_500(self):
        self.client.login(username='admvo2', password='clave-segura-123')
        response = self.client.get(reverse('pdf', args=[999999]))
        self.assertEqual(response.status_code, 404)


# ──────────────────────────────────────────────────────────────
# ALTA DE ALUMNOS
# ──────────────────────────────────────────────────────────────

class AlumnosTests(TestCase):
    def test_alta_valida_crea_alumno(self):
        datos = {
            'nombre': 'ALUMNO VALIDO',
            'numero_cuenta': '5556667',
            'carrera': 'MEDICO',
            'acepta_terminos': 'on',
        }
        response = self.client.post(reverse('registro_medicina'), datos)
        self.assertEqual(response.status_code, 302)
        alumno = Alumno.objects.get(numero_cuenta='5556667')
        self.assertEqual(alumno.facultad, 'MEDICINA')

    def test_registro_sin_aceptar_terminos_no_crea_alumno(self):
        datos = {
            'nombre': 'ALUMNO SIN TERMINOS',
            'numero_cuenta': '8889990',
            'carrera': 'MEDICO',
        }
        response = self.client.post(reverse('registro_medicina'), datos)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Alumno.objects.filter(numero_cuenta='8889990').exists())

    def test_registro_sin_nombre_no_crea_alumno(self):
        datos = {
            'numero_cuenta': '1231231',
            'carrera': 'MEDICO',
            'acepta_terminos': 'on',
        }
        response = self.client.post(reverse('registro_medicina'), datos)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Alumno.objects.filter(numero_cuenta='1231231').exists())

    def test_alta_no_afecta_alumnos_existentes(self):
        existente = _crear_alumno(numero_cuenta='0000001')
        datos = {
            'nombre': 'OTRO MAS',
            'numero_cuenta': '0000002',
            'carrera': 'MEDICO',
            'acepta_terminos': 'on',
        }
        self.client.post(reverse('registro_quimica'), datos)
        existente.refresh_from_db()
        self.assertEqual(existente.numero_cuenta, '0000001')
        self.assertEqual(Alumno.objects.count(), 2)
