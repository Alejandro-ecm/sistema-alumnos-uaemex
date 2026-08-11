import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Crea o actualiza el superusuario a partir de variables de entorno (sin valores por defecto inseguros)'

    def handle(self, *args, **kwargs):
        usuario  = os.environ.get('ADMIN_USER')
        password = os.environ.get('ADMIN_PASS')
        email    = os.environ.get('ADMIN_EMAIL', '')

        # Sin ADMIN_USER/ADMIN_PASS no se crea ni se toca ningún superusuario:
        # antes este comando caía en una contraseña fija conocida
        # ("FMQ.2026.admin") en cada despliegue si faltaban las variables.
        # Se prefiere no tocar la cuenta existente a reintroducir una
        # contraseña débil y pública en el historial de Git.
        if not usuario or not password:
            self.stdout.write(self.style.WARNING(
                'ADMIN_USER y/o ADMIN_PASS no están configurados: no se creó ni '
                'modificó ningún superusuario. Define ambas variables de entorno '
                'si necesitas que este comando administre la cuenta.'
            ))
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(username=usuario)
        if email:
            user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        accion = 'creado' if created else 'actualizado'
        self.stdout.write(self.style.SUCCESS(
            f'Superusuario "{usuario}" {accion} correctamente.'
        ))
