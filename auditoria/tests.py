from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno, ImpresionConstancia
from catalogo.models import Ejemplar, RegistroBibliografico
from circulacion.models import Prestamo

from .admin import RegistroAuditoriaAdmin
from .models import RegistroAuditoria

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
# SEÑALES SOBRE ALUMNO
# ──────────────────────────────────────────────────────────────

class RegistroAuditoriaAlumnoTests(TestCase):
    def test_crear_alumno_genera_registro_crear(self):
        alumno = _crear_alumno(numero_cuenta='9000001', nombre='ALUMNO AUDITORIA')
        registro = RegistroAuditoria.objects.get(
            content_type__model='alumno', object_id=alumno.pk, accion='CREAR'
        )
        self.assertEqual(registro.objeto_repr, 'ALUMNO AUDITORIA')

    def test_modificar_alumno_genera_registro_modificar(self):
        alumno = _crear_alumno(numero_cuenta='9000002')
        alumno.nombre = 'NOMBRE MODIFICADO'
        alumno.save()
        registro = RegistroAuditoria.objects.filter(
            content_type__model='alumno', object_id=alumno.pk, accion='MODIFICAR'
        ).latest('fecha_hora')
        self.assertEqual(registro.objeto_repr, 'NOMBRE MODIFICADO')

    def test_eliminar_alumno_genera_registro_eliminar(self):
        alumno = _crear_alumno(numero_cuenta='9000003')
        pk, nombre = alumno.pk, alumno.nombre
        alumno.delete()
        registro = RegistroAuditoria.objects.get(
            content_type__model='alumno', object_id=pk, accion='ELIMINAR'
        )
        self.assertEqual(registro.objeto_repr, nombre)


# ──────────────────────────────────────────────────────────────
# CABLEADO GENÉRICO ENTRE APPS (catalogo)
# ──────────────────────────────────────────────────────────────

class RegistroAuditoriaCatalogoTests(TestCase):
    def test_crear_ejemplar_en_otra_app_tambien_se_audita(self):
        registro_biblio = RegistroBibliografico.objects.create(titulo='Libro de auditoría')
        ejemplar = Ejemplar.objects.create(registro=registro_biblio, codigo_barras='EJ-AUD-0001')
        registro = RegistroAuditoria.objects.get(
            content_type__model='ejemplar', object_id=ejemplar.pk, accion='CREAR'
        )
        self.assertIn('EJ-AUD-0001', registro.objeto_repr)


# ──────────────────────────────────────────────────────────────
# CASO ESPECIAL: circulacion.Prestamo (llamadas explícitas, no señal)
# ──────────────────────────────────────────────────────────────

class RegistroAuditoriaPrestamoTests(TestCase):
    def setUp(self):
        self.alumno = _crear_alumno(numero_cuenta='9000004')
        registro_biblio = RegistroBibliografico.objects.create(titulo='Libro para préstamo auditado')
        self.ejemplar1 = Ejemplar.objects.create(registro=registro_biblio, codigo_barras='EJ-AUD-0002')
        self.ejemplar2 = Ejemplar.objects.create(registro=registro_biblio, codigo_barras='EJ-AUD-0003')

    def test_crear_prestamo_genera_registro_crear(self):
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar1, alumno=self.alumno)
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                content_type__model='prestamo', object_id=prestamo.pk, accion='CREAR'
            ).exists()
        )

    def test_marcar_devuelto_genera_registro_modificar(self):
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar1, alumno=self.alumno)
        prestamo.marcar_devuelto()
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                content_type__model='prestamo', object_id=prestamo.pk, accion='MODIFICAR'
            ).exists()
        )

    def test_marcar_perdido_genera_registro_modificar(self):
        prestamo = Prestamo.objects.create(ejemplar=self.ejemplar2, alumno=self.alumno)
        prestamo.marcar_perdido()
        self.assertTrue(
            RegistroAuditoria.objects.filter(
                content_type__model='prestamo', object_id=prestamo.pk, accion='MODIFICAR'
            ).exists()
        )


# ──────────────────────────────────────────────────────────────
# EL REGISTRO SOBREVIVE AL BORRADO DEL OBJETO AUDITADO
# ──────────────────────────────────────────────────────────────

class RegistroPreservadoTrasEliminarTests(TestCase):
    def test_registro_conserva_repr_y_objeto_resuelve_a_none(self):
        alumno = _crear_alumno(numero_cuenta='9000005', nombre='ALUMNO A BORRAR')
        pk = alumno.pk
        alumno.delete()

        registro = RegistroAuditoria.objects.get(
            content_type__model='alumno', object_id=pk, accion='ELIMINAR'
        )
        self.assertEqual(registro.objeto_repr, 'ALUMNO A BORRAR')
        self.assertIsNone(registro.objeto)


# ──────────────────────────────────────────────────────────────
# ATRIBUCIÓN DE USUARIO
# ──────────────────────────────────────────────────────────────

class UsuarioAtribuidoTests(TestCase):
    def setUp(self):
        self.alumno = _crear_alumno(numero_cuenta='9000006')
        self.admvo = User.objects.create_user(
            username='admvo_audit_user', password='clave-segura-123', is_staff=True
        )
        self.admvo.groups.add(Group.objects.get(name='Administrativos'))

    def test_cambio_via_peticion_autenticada_se_atribuye_al_usuario(self):
        self.client.login(username='admvo_audit_user', password='clave-segura-123')
        self.client.get(reverse('pdf', args=[self.alumno.id]))

        registro = RegistroAuditoria.objects.filter(
            content_type__model='impresionconstancia'
        ).latest('fecha_hora')
        self.assertEqual(registro.usuario, self.admvo)


class UsuarioNuloFueraDePeticionTests(TestCase):
    def test_cambio_fuera_de_una_peticion_no_tiene_usuario(self):
        alumno = _crear_alumno(numero_cuenta='9000007')
        registro = RegistroAuditoria.objects.get(
            content_type__model='alumno', object_id=alumno.pk, accion='CREAR'
        )
        self.assertIsNone(registro.usuario)


# ──────────────────────────────────────────────────────────────
# ADMIN DE SOLO LECTURA
# ──────────────────────────────────────────────────────────────

class AdminRegistroAuditoriaTests(TestCase):
    def setUp(self):
        self.admvo = User.objects.create_user(
            username='admvo_audit_admin', password='clave-segura-123', is_staff=True
        )
        self.admvo.groups.add(Group.objects.get(name='Administrativos'))
        self.sin_permiso = User.objects.create_user(
            username='staff_sin_audit', password='clave-segura-123', is_staff=True
        )

    def test_administrativo_puede_ver_el_changelist(self):
        self.client.login(username='admvo_audit_admin', password='clave-segura-123')
        response = self.client.get(reverse('admin:auditoria_registroauditoria_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_staff_sin_permiso_no_puede_ver_el_changelist(self):
        self.client.login(username='staff_sin_audit', password='clave-segura-123')
        response = self.client.get(reverse('admin:auditoria_registroauditoria_changelist'))
        self.assertEqual(response.status_code, 403)

    def test_admin_no_permite_alta_edicion_ni_borrado(self):
        modeladmin = RegistroAuditoriaAdmin(RegistroAuditoria, admin.site)
        self.assertFalse(modeladmin.has_add_permission(None))
        self.assertFalse(modeladmin.has_change_permission(None))
        self.assertFalse(modeladmin.has_delete_permission(None))
