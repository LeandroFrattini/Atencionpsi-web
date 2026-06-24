from django.utils import timezone
from django.db import transaction


class VisitaMiddleware:
    """Cuenta visitas por página y por día, ignorando el admin."""

    IGNORAR = ('/admin/', '/wa/', '/static/', '/media/', '/favicon')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Solo contar GETs exitosos, fuera del admin y recursos estáticos
        if (request.method == 'GET'
                and response.status_code == 200
                and not any(request.path.startswith(p) for p in self.IGNORAR)):
            try:
                from .models import Visita
                hoy = timezone.localdate()
                with transaction.atomic():
                    visita, created = Visita.objects.get_or_create(
                        fecha=hoy,
                        pagina=request.path,
                        defaults={'cantidad': 1}
                    )
                    if not created:
                        Visita.objects.filter(pk=visita.pk).update(cantidad=visita.cantidad + 1)
            except Exception:
                pass  # Nunca romper el sitio por analytics

        return response
