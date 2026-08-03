from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect

from profesionales.models import Psicologo


def psicologo_requerido(view_func=None, *, permitir_cambio_pendiente=False):
    """
    Exige login y resuelve el Psicologo ligado al usuario logueado, pasándolo
    como primer argumento posicional de la vista. Si el usuario logueado no
    tiene un Psicologo asociado, hay dos casos: si es la cuenta de la dueña
    del sitio (superuser), la mandamos a su propio panel general en vez de
    a una pantalla de error -- no tiene agenda propia porque su rol acá es
    controlar todo, no atender pacientes. Cualquier otra cuenta sin
    Psicologo asociado sí es un error real y se la saca del portal.

    Si el psicólogo todavía tiene una contraseña provisoria pendiente de
    cambio (`debe_cambiar_password`), lo manda directo a cambiarla antes de
    dejarlo ver cualquier otra pantalla — salvo que la vista sea justamente
    la de cambio de contraseña (`permitir_cambio_pendiente=True`).
    """
    def decorator(view_func):
        @login_required(login_url='portal_login')
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                psico = request.user.psicologo
            except Psicologo.DoesNotExist:
                if request.user.is_superuser:
                    return redirect('portal_admin_dashboard')
                messages.error(request, 'Esta cuenta no tiene un perfil de psicólogo asociado.')
                return redirect('portal_login')
            if psico.debe_cambiar_password and not permitir_cambio_pendiente:
                return redirect('portal_cambiar_password')
            return view_func(request, psico, *args, **kwargs)
        return wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator


def superuser_requerido(view_func):
    """
    Para las vistas del panel general de la dueña del sitio: exige login y
    que la cuenta sea superuser. Un psicólogo común que adivine la URL no
    tiene por qué ver ni tocar el estado de los demás profesionales.
    """
    @login_required(login_url='portal_login')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'No tenés permiso para ver esta página.')
            return redirect('portal_login')
        return view_func(request, *args, **kwargs)
    return wrapper
