from django import template
from django.contrib.auth.models import User
from django.urls import reverse
from alumnos.models import Alumno

register = template.Library()

ROLES_USUARIO = ['Administrativos', 'Mantenimiento', 'Bibliotecario']


@register.simple_tag
def total_alumnos():
    return Alumno.objects.count()


@register.inclusion_tag('admin/_usuarios_tabla.html')
def usuarios_tabla():
    usuarios = []
    for u in User.objects.order_by('username'):
        grupo_actual = u.groups.filter(name__in=ROLES_USUARIO).first()
        usuarios.append({
            'obj': u,
            'rol_actual': grupo_actual.name if grupo_actual else '',
            'cambiar_rol_url': reverse('admin:auth_user_cambiar_rol', args=[u.pk]),
            'eliminar_url': reverse('admin:auth_user_delete', args=[u.pk]),
            'editar_url': reverse('admin:auth_user_change', args=[u.pk]),
        })
    return {
        'usuarios': usuarios,
        'roles': ROLES_USUARIO,
        'add_url': reverse('admin:auth_user_add'),
    }
