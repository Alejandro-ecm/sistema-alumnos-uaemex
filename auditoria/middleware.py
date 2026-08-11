import threading

_local = threading.local()


def get_current_user():
    return getattr(_local, 'user', None)


class UsuarioActualMiddleware:
    """Guarda request.user en una variable thread-local para que registrar()
    pueda atribuir el autor del cambio incluso desde señales, que no reciben
    el request. Debe ir después de AuthenticationMiddleware en MIDDLEWARE."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        _local.user = user if user and user.is_authenticated else None
        try:
            return self.get_response(request)
        finally:
            _local.user = None
