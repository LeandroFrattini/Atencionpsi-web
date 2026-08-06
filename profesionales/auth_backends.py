from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailCaseInsensitiveBackend(ModelBackend):
    """
    El username de cada profesional siempre es el email que se cargó
    (ver Psicologo.usuario). Bastante gente lo escribe con mayúsculas
    distintas a como quedó guardado -- o el celular se lo autocompleta
    con mayúscula inicial -- y con la comparación exacta de siempre eso
    hacía fallar el login aunque la contraseña fuera correcta. Este
    backend busca sin importar mayúsculas/minúsculas.

    axes.backends.AxesStandaloneBackend va primero en
    AUTHENTICATION_BACKENDS y NO verifica contraseña -- solo controla
    bloqueos por intentos fallidos y le pasa la posta al siguiente
    backend de la lista. Este reemplaza a ese siguiente backend
    (ModelBackend), así que no interfiere con el bloqueo de axes.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # No debería pasar (username es único), pero ante la duda no
            # dejamos pasar un login ambiguo.
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
