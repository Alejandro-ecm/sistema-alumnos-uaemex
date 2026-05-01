import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Crea o actualiza superusuario desde variables de entorno'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        usuario  = os.environ.get('ADMIN_USER',  'admin')
        email    = os.environ.get('ADMIN_EMAIL', 'admin@uaemex.mx')
        password = os.environ.get('ADMIN_PASS',  'uaemex2026')

        user, created = User.objects.get_or_create(username=usuario)
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        accion = 'creado' if created else 'actualizado'
        self.stdout.write(self.style.SUCCESS(
            f'Superusuario "{usuario}" {accion} correctamente.'
        ))
