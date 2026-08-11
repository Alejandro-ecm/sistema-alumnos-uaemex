from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as serve_media

from alumnos.views import panel_redirect

urlpatterns = [
    path('admin/', panel_redirect),
    path('admin/', admin.site.urls),
    path('', include('alumnos.urls')),
    # Servido explícitamente (no vía el helper static() de Django, que se
    # desactiva por completo cuando DEBUG=False) porque el proyecto no tiene
    # todavía un almacenamiento de media dedicado (CDN/objeto) en producción.
    re_path(r'^media/(?P<path>.*)$', serve_media, {'document_root': settings.MEDIA_ROOT}),
]