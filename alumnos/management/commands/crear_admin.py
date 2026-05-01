import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Crea superusuario desde variables de entorno'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        usuario  = os.environ.get('ADMIN_USER',  'admin')
        email    = os.environ.get('ADMIN_EMAIL', 'admin@uaemex.mx')
        password = os.environ.get('ADMIN_PASS',  'uaemex2026')
        if not User.objects.filter(username=usuario).exists():
            User.objects.create_superuser(usuario, email, password)
            self.stdout.write(self.style.SUCCESS(f'Superusuario "{usuario}" creado.'))
        else:
            self.stdout.write(f'El usuario "{usuario}" ya existe.')
