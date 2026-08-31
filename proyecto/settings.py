from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Carpeta de datos persistentes (base de datos SQLite + archivos subidos).
# En local usa BASE_DIR; en Railway define DATA_DIR=/data y monta un Volumen ahí
# para que los datos NO se borren en cada despliegue.
DATA_DIR = Path(os.environ.get('DATA_DIR', BASE_DIR))

# DEBUG por defecto en False: si la variable de entorno no está definida,
# el sistema debe arrancar seguro (sin tracebacks/DEBUG expuestos), no al revés.
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        # Solo para desarrollo local sin variables de entorno configuradas.
        SECRET_KEY = 'django-insecure-4e!z4e&r1@ipwwherj*rvfe2vs1g$21t9@_qa=^lj%b-g+9^qd'
    else:
        raise ImproperlyConfigured(
            'SECRET_KEY no está definido. Configura la variable de entorno SECRET_KEY '
            'antes de ejecutar el sistema con DEBUG=False (producción).'
        )

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get(
        'ALLOWED_HOSTS',
        'titulacion.skytechnologieslatam.com,.railway.app,.up.railway.app,localhost,127.0.0.1'
    ).split(',') if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    'https://titulacion.skytechnologieslatam.com',
    'https://*.railway.app',
    'https://*.up.railway.app',
]

# Cookies de sesión/CSRF solo por HTTPS cuando no estamos en desarrollo local.
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'auditoria',
    'alumnos',
    'deteccion_libros',
    'catalogo',
    'circulacion',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'auditoria.middleware.UsuarioActualMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'proyecto.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'proyecto.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGOUT_REDIRECT_URL = '/admin/login/'
LOGIN_URL = '/admin/login/'
# El login.html de Jazzmin no manda el campo oculto "next" cuando no venía
# en la URL, así que sin esto Django cae en el default '/accounts/profile/'
# (inexistente) y muestra 404 tras iniciar sesión.
LOGIN_REDIRECT_URL = '/admin/'

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = DATA_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Envío de correo (botón "Enviar correo" con las constancias en PDF al alumno).
# En Railway define EMAIL_HOST_USER / EMAIL_HOST_PASSWORD (contraseña de
# aplicación, no la contraseña normal de la cuenta) como variables de entorno.
# Sin esas variables, en desarrollo local (DEBUG=True) los correos solo se
# imprimen en la consola en vez de enviarse de verdad.
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'boxpipo658@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-responder@uaemex.mx')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
elif DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

JAZZMIN_SETTINGS = {
    "site_title": "UAEMex – Titulación",
    "site_header": "Facultad de Medicina y Química",
    "site_brand": "UAEMex",
    "welcome_sign": "Bienvenido al panel administrativo",
    "site_logo": "img/logo.JPG",
    "site_logo_classes": "img-circle",
    "site_icon": "img/logo.JPG",
    "login_logo": None,
    "login_logo_dark": None,
    "login_show_bg_image": False,
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "alumnos.alumno": "fas fa-user-graduate",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users",
    },
    "related_modal_active": True,
    "order_with_respect_to": ["auth", "alumnos"],
    "copyright": "Facultad de Medicina y Química – UAEMex 2026",
    "custom_links": {
        "deteccion_libros": [{
            "name": "Vista de seguridad",
            "url": "admin:deteccion_libros_vista_seguridad",
            "icon": "fas fa-video",
            "permissions": ["deteccion_libros.view_eventodeteccion"],
        }],
        "catalogo": [{
            "name": "MARC21",
            "url": "admin:catalogo_marc21",
            "icon": "fas fa-book",
            "permissions": ["catalogo.view_registrobibliografico"],
        }, {
            "name": "Acervo Digital",
            "url": "/admin/catalogo/registrobibliografico/panel-biblioteca/?tab=acervo",
            "icon": "fas fa-book-reader",
            "permissions": ["catalogo.view_registrobibliografico"],
        }],
    },
    "hide_models": [
        "auth.user",
        "deteccion_libros.eventodeteccion",
        "catalogo.autor",
        "catalogo.editorial",
        "catalogo.materia",
        "catalogo.ejemplar",
        "catalogo.constanciadonacion",
        "catalogo.registrobibliografico",
    ],
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-success",
    "accent": "accent-success",
    "navbar_colour": "navbar-dark navbar-success",
    "sidebar_colour": "sidebar-dark-success",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_legacy_style": False,
    "footer_colour": "footer-light",
    "show_sidebar": True,
    "theme": "flatly",
}
