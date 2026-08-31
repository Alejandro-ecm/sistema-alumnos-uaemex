from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .admin import EventoDeteccionAdmin
from .models import EventoDeteccion

User = get_user_model()

# GIF de 1x1 transparente: el ImageField de EventoDeteccion es obligatorio
# (sin blank=True/null=True) y Pillow valida el contenido real del archivo,
# así que no basta con un archivo de texto disfrazado.
_GIF_1X1 = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04'
    b'\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def _imagen_valida(nombre='evidencia.gif'):
    return SimpleUploadedFile(nombre, _GIF_1X1, content_type='image/gif')


def _crear_evento(**overrides):
    datos = dict(
        tipo='robo',
        fuente='Cámara pasillo',
        confianza=0.9,
        imagen_evidencia=_imagen_valida(),
    )
    datos.update(overrides)
    return EventoDeteccion.objects.create(**datos)


# ──────────────────────────────────────────────────────────────
# MODELO
# ──────────────────────────────────────────────────────────────

class EventoDeteccionModeloTests(TestCase):
    def test_valores_por_defecto_al_crear(self):
        evento = _crear_evento()
        self.assertFalse(evento.revisado)
        self.assertIsNotNone(evento.fecha_hora)

    def test_str_incluye_tipo_y_fuente(self):
        evento = _crear_evento(tipo='ruptura', fuente='Cámara mostrador')
        self.assertIn('Cámara mostrador', str(evento))
        self.assertIn('ruptura', str(evento).lower())


# ──────────────────────────────────────────────────────────────
# MÉTODOS DE VISUALIZACIÓN DEL ADMIN
# ──────────────────────────────────────────────────────────────

class EventoDeteccionAdminDisplayTests(TestCase):
    def setUp(self):
        self.modeladmin = EventoDeteccionAdmin(EventoDeteccion, admin.site)

    def test_miniatura_sin_imagen_muestra_guion(self):
        evento = EventoDeteccion(tipo='robo', fuente='Cámara sin imagen', confianza=0.5)
        self.assertEqual(self.modeladmin.miniatura(evento), '—')

    def test_miniatura_con_imagen_incluye_tag_img(self):
        evento = _crear_evento()
        self.assertIn('<img', self.modeladmin.miniatura(evento))
        self.assertIn(evento.imagen_evidencia.url, self.modeladmin.miniatura(evento))

    def test_vista_previa_sin_imagen(self):
        evento = EventoDeteccion(tipo='robo', fuente='Cámara sin imagen', confianza=0.5)
        self.assertEqual(self.modeladmin.vista_previa(evento), 'Sin imagen')

    def test_vista_previa_con_imagen_incluye_tag_img(self):
        evento = _crear_evento()
        self.assertIn('<img', self.modeladmin.vista_previa(evento))

    def test_tipo_badge_robo_usa_color_rojo(self):
        evento = _crear_evento(tipo='robo')
        self.assertIn('#c62828', self.modeladmin.tipo_badge(evento))
        self.assertIn('Posible sustracción de libro', self.modeladmin.tipo_badge(evento))

    def test_tipo_badge_ruptura_usa_color_ambar(self):
        evento = _crear_evento(tipo='ruptura')
        self.assertIn('#b8973a', self.modeladmin.tipo_badge(evento))
        self.assertIn('Posible ruptura de páginas', self.modeladmin.tipo_badge(evento))

    def test_confianza_pct_formatea_como_porcentaje_entero(self):
        evento = _crear_evento(confianza=0.42)
        self.assertEqual(self.modeladmin.confianza_pct(evento), '42%')


# ──────────────────────────────────────────────────────────────
# ACCESO A LA VISTA DE SEGURIDAD
# ──────────────────────────────────────────────────────────────

class VistaSeguridadAccessTests(TestCase):
    def setUp(self):
        self.mant = User.objects.create_user(
            username='mant_deteccion', password='clave-segura-123', is_staff=True
        )
        self.mant.groups.add(Group.objects.get(name='Superusuario'))
        self.sin_permiso = User.objects.create_user(
            username='staff_sin_deteccion', password='clave-segura-123', is_staff=True
        )

    def test_anonimo_es_redirigido_al_login(self):
        response = self.client.get(reverse('admin:deteccion_libros_vista_seguridad'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_staff_sin_permiso_recibe_403(self):
        self.client.login(username='staff_sin_deteccion', password='clave-segura-123')
        response = self.client.get(reverse('admin:deteccion_libros_vista_seguridad'))
        self.assertEqual(response.status_code, 403)

    def test_mantenimiento_accede_con_camaras_y_puerto_en_contexto(self):
        self.client.login(username='mant_deteccion', password='clave-segura-123')
        with patch('deteccion_libros.admin._leer_camaras', return_value=[{'nombre': 'Cam1'}]):
            response = self.client.get(reverse('admin:deteccion_libros_vista_seguridad'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['camaras'], [{'nombre': 'Cam1'}])
        self.assertEqual(response.context['puerto_stream'], 8090)


# ──────────────────────────────────────────────────────────────
# GUARDAR CÁMARA (sin tocar vision/camaras.json real)
# ──────────────────────────────────────────────────────────────

class GuardarCamaraTests(TestCase):
    def setUp(self):
        self.mant = User.objects.create_user(
            username='mant_guardar_camara', password='clave-segura-123', is_staff=True
        )
        self.mant.groups.add(Group.objects.get(name='Superusuario'))
        self.client.login(username='mant_guardar_camara', password='clave-segura-123')

    def test_falta_nombre_o_source_devuelve_400_y_no_persiste(self):
        with patch('deteccion_libros.admin._leer_camaras', return_value=[]) as mock_leer, \
                patch('deteccion_libros.admin._guardar_camaras') as mock_guardar:
            response = self.client.post(
                reverse('admin:deteccion_libros_guardar_camara'), {'nombre': '', 'source': ''}
            )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        mock_guardar.assert_not_called()

    def test_payload_valido_agrega_camara_nueva(self):
        with patch('deteccion_libros.admin._leer_camaras', return_value=[]), \
                patch('deteccion_libros.admin._guardar_camaras') as mock_guardar:
            response = self.client.post(reverse('admin:deteccion_libros_guardar_camara'), {
                'nombre': 'Celular pasillo',
                'source': 'rtsp://192.168.1.50/stream',
                'activa': '1',
            })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        mock_guardar.assert_called_once_with([{
            'nombre': 'Celular pasillo',
            'source': 'rtsp://192.168.1.50/stream',
            'activa': True,
            'zona_salida': None,
        }])
