from django import template
from alumnos.models import Alumno

register = template.Library()


@register.simple_tag
def total_alumnos():
    return Alumno.objects.count()
