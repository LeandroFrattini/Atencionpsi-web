from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

from .models import IngresoPortal


@receiver(user_logged_in)
def registrar_ingreso_portal(sender, request, user, **kwargs):
    """
    Cuenta un ingreso al portal por profesional y por día -- para ver si la
    agenda se usa o no. La cuenta de la dueña del sitio (superuser, sin
    Psicologo asociado) no tiene 'psicologo' así que no se cuenta acá.
    """
    psico = getattr(user, 'psicologo', None)
    if not psico:
        return
    try:
        hoy = timezone.localdate()
        ingreso, created = IngresoPortal.objects.get_or_create(
            fecha=hoy, psicologo=psico, defaults={'cantidad': 1}
        )
        if not created:
            IngresoPortal.objects.filter(pk=ingreso.pk).update(cantidad=ingreso.cantidad + 1)
    except Exception:
        pass
