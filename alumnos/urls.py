from django.urls import path
from .views import seleccion, registro, gracias, generar_pdf, generar_pdf2, generar_carta, lista_alumnos

urlpatterns = [
    path('', seleccion, name='seleccion'),
    path('medicina/', registro, {'facultad': 'MEDICINA'}, name='registro_medicina'),
    path('quimica/', registro,  {'facultad': 'QUIMICA'},  name='registro_quimica'),
    path('gracias/<int:alumno_id>/', gracias, name='gracias'),
    path('pdf/<int:alumno_id>/',    generar_pdf,    name='pdf'),
    path('pdf2/<int:alumno_id>/',   generar_pdf2,   name='pdf2'),
    path('carta/<int:alumno_id>/',  generar_carta,  name='carta'),
]
