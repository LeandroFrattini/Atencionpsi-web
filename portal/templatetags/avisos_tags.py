import datetime

from django import template
from django.utils import timezone

from portal.models import Turno

register = template.Library()


@register.simple_tag
def reservas_sin_aviso():
    """Reservas de la web de los últimos 15 días cuyo mail de aviso al profesional NO salió (con el error anotado)."""
    desde = timezone.now() - datetime.timedelta(days=15)
    return Turno.objects.filter(
        origen='publico', creado_en__gte=desde, aviso_enviado_en__isnull=True,
    ).exclude(aviso_error='').count()
