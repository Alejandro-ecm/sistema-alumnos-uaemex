import base64
import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalogo.models import Ejemplar, RegistroBibliografico
from circulacion.services import crear_prestamo

from .models import Alumno, ImpresionConstancia

User = get_user_model()

_PNG_1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
)


def _crear_alumno(**overrides):
    datos = dict(
        nombre='ALUMNO DE PRUEBA',
        numero_cuenta='1234567',
        carrera='MEDICO',
        facultad='MEDICINA',
    )
    datos.update(overrides)
    return Alumno.objects.create(**datos)


def _datos_libro_validos():
    """Campos requeridos del cuestionario (correo institucional + datos del
    libro, sección 4 de registro.html) para que un POST a `registro` sea válido."""
    return {
        'correo': 'alumno.prueba@alumno.uaemex.mx',
        'libro_titulo': 'Anatomía Humana',
        'libro_autor': 'Latarjet',
        'libro_editorial': 'Panamericana',
        'libro_edicion': '5a edición',
        'libro_portada': SimpleUploadedFile('portada.png', _PNG_1PX, content_type='image/png'),
    }


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

        self.superusuario = User.objects.create_user(
            username='mant1', password='clave-segura-123', is_staff=True
        )
        self.superusuario.groups.add(Group.objects.get(name='Superusuario'))

        self.biblio = User.objects.create_user(
            username='biblio1', password='clave-segura-123', is_staff=True
        )
        self.biblio.groups.add(Group.objects.get(name='Bibliotecario'))

        self.sin_grupo = User.objects.create_user(
            username='staffsin', password='clave-segura-123', is_staff=True
        )

    def test_administrativo_accede_al_listado_de_alumnos(self):
        self.client.login(username='admvo1', password='clave-segura-123')
        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_superusuario_accede_a_panel_mantenimiento(self):
        self.client.login(username='mant1', password='clave-segura-123')
        response = self.client.get(reverse('admin:deteccion_libros_panel_mantenimiento'))
        self.assertEqual(response.status_code, 200)

    def test_administrativo_no_accede_a_vista_de_seguridad(self):
        self.client.login(username='admvo1', password='clave-segura-123')
        response = self.client.get(reverse('admin:deteccion_libros_vista_seguridad'))
        self.assertEqual(response.status_code, 403)

    def test_superusuario_accede_al_listado_de_alumnos(self):
        # El rol 'Superusuario' tiene is_superuser=True (ver alumnos/signals.py),
        # así que no está limitado como los demás roles: accede a todo el admin.
        self.client.login(username='mant1', password='clave-segura-123')
        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_staff_sin_grupo_no_accede_a_panel_mantenimiento(self):
        self.client.login(username='staffsin', password='clave-segura-123')
        response = self.client.get(reverse('admin:deteccion_libros_panel_mantenimiento'))
        self.assertEqual(response.status_code, 403)

    def test_bibliotecario_accede_al_listado_de_registros_bibliograficos(self):
        self.client.login(username='biblio1', password='clave-segura-123')
        response = self.client.get(reverse('admin:catalogo_registrobibliografico_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_bibliotecario_accede_al_listado_de_prestamos(self):
        self.client.login(username='biblio1', password='clave-segura-123')
        response = self.client.get(reverse('admin:circulacion_prestamo_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_bibliotecario_no_accede_al_listado_de_alumnos(self):
        self.client.login(username='biblio1', password='clave-segura-123')
        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertEqual(response.status_code, 403)

    def test_bibliotecario_accede_a_su_panel(self):
        self.client.login(username='biblio1', password='clave-segura-123')
        response = self.client.get(reverse('admin:catalogo_panel_biblioteca'))
        self.assertEqual(response.status_code, 200)

    def test_administrativo_accede_al_acervo_digital(self):
        # Administrativos tiene catalogo.view_registrobibliografico (solo
        # lectura) para que el Acervo/Catálogo Digital esté disponible en
        # los 3 roles de acceso, no solo para Bibliotecario (Superusuario
        # ya lo tiene todo por ser is_superuser=True).
        self.client.login(username='admvo1', password='clave-segura-123')
        response = self.client.get(reverse('admin:catalogo_panel_biblioteca'))
        self.assertEqual(response.status_code, 200)


# ──────────────────────────────────────────────────────────────
# ATERRIZAJE EN /admin/ SEGÚN ROL
# ──────────────────────────────────────────────────────────────

class PanelRedirectPorRolTests(TestCase):
    def test_bibliotecario_es_redirigido_a_su_panel(self):
        biblio = User.objects.create_user(username='biblio_redir', password='clave-segura-123', is_staff=True)
        biblio.groups.add(Group.objects.get(name='Bibliotecario'))
        self.client.login(username='biblio_redir', password='clave-segura-123')
        response = self.client.get('/admin/')
        self.assertRedirects(response, reverse('admin:catalogo_panel_biblioteca'))

    def test_superusuario_llega_directo_al_indice_del_admin(self):
        # is_superuser=True cae en la primera rama de panel_redirect: el
        # índice normal del admin con todas las secciones, no un panel propio.
        superusuario = User.objects.create_user(
            username='superusuario_redir', password='clave-segura-123', is_staff=True
        )
        superusuario.groups.add(Group.objects.get(name='Superusuario'))
        self.client.login(username='superusuario_redir', password='clave-segura-123')
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detección')


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
            **_datos_libro_validos(),
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
            **_datos_libro_validos(),
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
            **_datos_libro_validos(),
        }
        self.client.post(reverse('registro_quimica'), datos)
        existente.refresh_from_db()
        self.assertEqual(existente.numero_cuenta, '0000001')
        self.assertEqual(Alumno.objects.count(), 2)


# ──────────────────────────────────────────────────────────────
# ESTADO DE BIBLIOTECA EN EL CHANGELIST (no_adeudo)
# ──────────────────────────────────────────────────────────────

class EstadoBibliotecaAdminTests(TestCase):
    def setUp(self):
        self.admvo = User.objects.create_user(
            username='admvo_biblio', password='clave-segura-123', is_staff=True
        )
        self.admvo.groups.add(Group.objects.get(name='Administrativos'))
        self.client.login(username='admvo_biblio', password='clave-segura-123')

    def test_alumno_sin_prestamos_muestra_sin_adeudo(self):
        _crear_alumno(numero_cuenta='7778889')
        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertContains(response, 'Sin adeudo')

    def test_alumno_con_prestamo_vencido_muestra_vencido(self):
        alumno = _crear_alumno(numero_cuenta='7778890')
        registro = RegistroBibliografico.objects.create(titulo='Libro de prueba admin')
        ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-ADMIN-0001')
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        crear_prestamo(
            alumno_nombre=alumno.nombre, matricula=alumno.numero_cuenta,
            fecha_devolucion=ayer, ejemplar_ids=[ejemplar.pk],
        )

        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertContains(response, 'vencido')

    def test_changelist_muestra_conteo_de_alumnos_con_adeudo(self):
        alumno = _crear_alumno(numero_cuenta='7778891')
        registro = RegistroBibliografico.objects.create(titulo='Libro de prueba conteo')
        ejemplar = Ejemplar.objects.create(registro=registro, codigo_barras='EJ-ADMIN-0002')
        ayer = timezone.now().date() - datetime.timedelta(days=1)
        crear_prestamo(
            alumno_nombre=alumno.nombre, matricula=alumno.numero_cuenta,
            fecha_devolucion=ayer, ejemplar_ids=[ejemplar.pk],
        )

        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertEqual(response.context['total_adeudos'], 1)

    def test_changelist_no_muestra_barra_de_acciones_en_lote(self):
        _crear_alumno(numero_cuenta='7778892', nombre='ALUMNO SIN ACCIONES')
        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertNotContains(response, 'action-select')

    def test_changelist_no_muestra_los_filtros_laterales(self):
        _crear_alumno(numero_cuenta='7778893', nombre='ALUMNO SIN FILTROS')
        response = self.client.get(reverse('admin:alumnos_alumno_changelist'))
        self.assertEqual(response.context['cl'].filter_specs, [])


# ──────────────────────────────────────────────────────────────
# ADMIN DE USUARIOS SIMPLIFICADO (alta/edición por rol)
# ──────────────────────────────────────────────────────────────

class UsuarioAdminTests(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_user(
            username='mant_admin', password='clave-segura-123', is_staff=True
        )
        self.superusuario.groups.add(Group.objects.get(name='Superusuario'))
        self.client.login(username='mant_admin', password='clave-segura-123')

    def test_formulario_de_alta_solo_muestra_los_campos_simplificados(self):
        response = self.client.get(reverse('admin:auth_user_add'))
        self.assertContains(response, 'id_rol')
        self.assertNotContains(response, 'id_is_superuser')
        self.assertNotContains(response, 'id_user_permissions')

    def test_alta_de_usuario_asigna_is_staff_y_el_grupo_del_rol_elegido(self):
        response = self.client.post(reverse('admin:auth_user_add'), {
            'username': 'nuevo_bibliotecario',
            'password1': 'ClaveSegura123!',
            'password2': 'ClaveSegura123!',
            'rol': 'Bibliotecario',
            'is_active': 'on',
            '_save': 'Guardar',
        })
        self.assertEqual(response.status_code, 302)
        nuevo = User.objects.get(username='nuevo_bibliotecario')
        self.assertTrue(nuevo.is_staff)
        self.assertEqual(list(nuevo.groups.values_list('name', flat=True)), ['Bibliotecario'])

    def test_editar_usuario_resincroniza_el_grupo_al_cambiar_de_rol(self):
        usuario = User.objects.create_user(username='cambia_rol', password='x', is_staff=True)
        usuario.groups.add(Group.objects.get(name='Bibliotecario'))

        response = self.client.post(reverse('admin:auth_user_change', args=[usuario.pk]), {
            'username': 'cambia_rol',
            'password': usuario.password,
            'rol': 'Administrativos',
            'is_active': 'on',
            '_save': 'Guardar',
        })
        self.assertEqual(response.status_code, 302)
        usuario.refresh_from_db()
        self.assertEqual(list(usuario.groups.values_list('name', flat=True)), ['Administrativos'])

    def test_desactivar_usuario_no_lo_borra(self):
        usuario = User.objects.create_user(username='se_desactiva', password='x', is_staff=True)
        usuario.groups.add(Group.objects.get(name='Bibliotecario'))

        response = self.client.post(reverse('admin:auth_user_change', args=[usuario.pk]), {
            'username': 'se_desactiva',
            'password': usuario.password,
            'rol': 'Bibliotecario',
            '_save': 'Guardar',
        })
        self.assertEqual(response.status_code, 302)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)
        self.assertTrue(User.objects.filter(pk=usuario.pk).exists())

    def test_eliminar_usuario_lo_borra_de_la_base_de_datos(self):
        usuario = User.objects.create_user(username='se_elimina', password='x', is_staff=True)
        response = self.client.post(reverse('admin:auth_user_delete', args=[usuario.pk]), {'post': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=usuario.pk).exists())

    def test_elegir_rol_superusuario_otorga_is_superuser(self):
        response = self.client.post(reverse('admin:auth_user_add'), {
            'username': 'nuevo_superusuario',
            'password1': 'ClaveSegura123!',
            'password2': 'ClaveSegura123!',
            'rol': 'Superusuario',
            'is_active': 'on',
            '_save': 'Guardar',
        })
        self.assertEqual(response.status_code, 302)
        nuevo = User.objects.get(username='nuevo_superusuario')
        self.assertTrue(nuevo.is_superuser)
        self.assertEqual(list(nuevo.groups.values_list('name', flat=True)), ['Superusuario'])

    def test_quitar_rol_superusuario_revoca_is_superuser(self):
        usuario = User.objects.create_user(username='deja_de_ser_superusuario', password='x', is_staff=True)
        usuario.groups.add(Group.objects.get(name='Superusuario'))
        self.assertTrue(User.objects.get(pk=usuario.pk).is_superuser)

        response = self.client.post(reverse('admin:auth_user_change', args=[usuario.pk]), {
            'username': 'deja_de_ser_superusuario',
            'password': usuario.password,
            'rol': 'Bibliotecario',
            'is_active': 'on',
            '_save': 'Guardar',
        })
        self.assertEqual(response.status_code, 302)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_superuser)


# ──────────────────────────────────────────────────────────────
# ENVIAR CORREO (botón "Enviar correo" en el listado de alumnos)
# ──────────────────────────────────────────────────────────────

class EnviarCorreoTests(TestCase):
    def setUp(self):
        self.admvo = User.objects.create_user(
            username='admvo_correo', password='clave-segura-123', is_staff=True
        )
        self.admvo.groups.add(Group.objects.get(name='Administrativos'))
        self.client.login(username='admvo_correo', password='clave-segura-123')
        self.alumno = _crear_alumno(numero_cuenta='7778999', correo='alumno@alumno.uaemex.mx')

    def _url(self):
        return reverse('admin:alumnos_alumno_enviar_correo', args=[self.alumno.pk])

    def test_get_muestra_el_formulario_con_el_correo_precargado(self):
        response = self.client.get(self._url())
        self.assertContains(response, 'value="alumno@alumno.uaemex.mx"')
        self.assertContains(response, 'Constancia de No Adeudo')
        self.assertContains(response, 'Registro de Material')
        self.assertContains(response, 'Carta de Autorización')

    def test_post_envia_solo_los_documentos_seleccionados_al_correo_editado(self):
        from django.core import mail

        response = self.client.post(self._url(), {
            'correo': 'otro@alumno.uaemex.mx',
            'documentos': ['NO_ADEUDO', 'CARTA_AUTORIZACION'],
        })
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        enviado = mail.outbox[0]
        self.assertEqual(enviado.to, ['otro@alumno.uaemex.mx'])
        self.assertEqual(len(enviado.attachments), 2)

        tipos_registrados = set(
            ImpresionConstancia.objects.filter(alumno=self.alumno).values_list('tipo', flat=True)
        )
        self.assertEqual(tipos_registrados, {'NO_ADEUDO', 'CARTA_AUTORIZACION'})

    def test_post_sin_documentos_seleccionados_no_envia_nada(self):
        from django.core import mail

        response = self.client.post(self._url(), {
            'correo': 'otro@alumno.uaemex.mx',
            'documentos': [],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
