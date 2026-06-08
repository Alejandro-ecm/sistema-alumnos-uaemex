from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Carpeta de datos persistentes (base de datos SQLite + archivos subidos).
# En local usa BASE_DIR; en Railway define DATA_DIR=/data y monta un Volumen ahí
# para que los datos NO se borren en cada despliegue.
DATA_DIR = Path(os.environ.get('DATA_DIR', BASE_DIR))

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-4e!z4e&r1@ipwwherj*rvfe2vs1g$21t9@_qa=^lj%b-g+9^qd')

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = [
    'https://skytechnologieslatam.com',
    'https://www.skytechnologieslatam.com',
    'https://*.railway.app',
    'https://*.up.railway.app',
]

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'alumnos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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

JAZZMIN_SETTINGS = {
    "site_title": "UAEMex – Titulación",
    "site_header": "Facultad de Medicina y Química",
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
