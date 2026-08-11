from django.apps import AppConfig


class CatalogoConfig(AppConfig):
    name = 'catalogo'

    def ready(self):
        from . import signals  # noqa: F401
