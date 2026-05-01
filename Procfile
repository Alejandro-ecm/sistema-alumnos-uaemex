web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py crear_admin && gunicorn proyecto.wsgi --bind 0.0.0.0:$PORT
