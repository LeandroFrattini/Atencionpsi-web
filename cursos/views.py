import json
import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from portal.decorators import psicologo_requerido

from . import mercadopago_checkout
from .forms import InscripcionPublicaForm
from .models import Curso, InscripcionCurso

logger = logging.getLogger(__name__)


def detalle_curso(request, slug):
    curso = get_object_or_404(Curso, slug=slug, activo=True)
    form = InscripcionPublicaForm()
    return render(request, 'cursos/detalle.html', {'curso': curso, 'form': form})


def inscripcion_publica(request, slug):
    curso = get_object_or_404(Curso, slug=slug, activo=True)
    if curso.agotado:
        messages.error(request, 'Este curso ya no tiene cupos disponibles.')
        return redirect('cursos_detalle', slug=slug)

    if request.method == 'POST':
        form = InscripcionPublicaForm(request.POST)
        if form.is_valid():
            inscripcion = InscripcionCurso.objects.create(
                curso=curso,
                nombre=form.cleaned_data['nombre'],
                email=form.cleaned_data['email'],
                whatsapp=form.cleaned_data['whatsapp'],
                es_red_consulta=False,
                monto=curso.precio_publico,
            )
            return _ir_a_mercadopago(request, inscripcion)
    else:
        form = InscripcionPublicaForm()
    return render(request, 'cursos/detalle.html', {'curso': curso, 'form': form})


@psicologo_requerido
def inscripcion_red_consulta(request, psico, slug):
    curso = get_object_or_404(Curso, slug=slug, activo=True)
    if curso.agotado:
        messages.error(request, 'Este curso ya no tiene cupos disponibles.')
        return redirect('cursos_detalle', slug=slug)

    if request.method == 'POST':
        inscripcion = InscripcionCurso.objects.create(
            curso=curso,
            psicologo=psico,
            nombre=psico.nombre,
            email=psico.usuario.email if psico.usuario else '',
            whatsapp=psico.whatsapp,
            es_red_consulta=True,
            monto=curso.precio_red_consulta,
        )
        return _ir_a_mercadopago(request, inscripcion)

    return render(request, 'cursos/confirmar_red_consulta.html', {'curso': curso, 'psico': psico})


def _ir_a_mercadopago(request, inscripcion):
    try:
        preferencia = mercadopago_checkout.crear_preferencia(inscripcion, request)
    except Exception:
        logger.exception('Error creando preferencia de Mercado Pago para inscripción %s', inscripcion.pk)
        messages.error(request, 'No se pudo iniciar el pago. Probá de nuevo en un momento.')
        return redirect('cursos_detalle', slug=inscripcion.curso.slug)

    inscripcion.mp_preference_id = preferencia['id']
    inscripcion.save(update_fields=['mp_preference_id'])

    if settings.DEBUG:
        # No hay forma de simular el checkout hosteado de Mercado Pago en
        # dev -- se muestra una pantalla para aprobar/rechazar a mano y
        # poder probar el resto del flujo (igual que el botón de "simular
        # pago" que ya existe para las suscripciones de profesionales).
        return render(request, 'cursos/simular_pago.html', {'inscripcion': inscripcion})

    return redirect(preferencia['init_point'])


def resultado(request, pk):
    inscripcion = get_object_or_404(InscripcionCurso, pk=pk)
    return render(request, 'cursos/resultado.html', {'inscripcion': inscripcion})


@require_POST
def simular_pago(request, pk):
    if not settings.DEBUG:
        raise Http404()
    inscripcion = get_object_or_404(InscripcionCurso, pk=pk)
    aprobar = request.POST.get('accion') == 'aprobar'
    if aprobar:
        # Con un valor fijo, la segunda simulación de pago (para cualquier
        # inscripción) pisaba el unique=True de mp_payment_id y tiraba un
        # IntegrityError -- solo pasa en DEBUG, nunca en producción (esta
        # vista ni siquiera existe ahí), pero rompía las pruebas manuales
        # locales apenas se simulaba un segundo pago.
        _confirmar_inscripcion(inscripcion, mp_payment_id=f'SIMULADO-DEV-{inscripcion.pk}')
    else:
        inscripcion.estado = 'rechazado'
        inscripcion.save(update_fields=['estado'])
    return redirect('cursos_resultado', pk=pk)


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    """Mercado Pago avisa acá cuando cambia el estado de un pago. Nunca hay
    que confiar ciegamente en lo que manda la notificación -- se vuelve a
    consultar el pago por su id para confirmar el estado real, tal como
    recomienda la documentación de Mercado Pago."""
    payment_id = request.GET.get('data.id') or request.GET.get('id')
    if not payment_id:
        try:
            cuerpo = json.loads(request.body or b'{}')
        except ValueError:
            return HttpResponseBadRequest('JSON inválido')
        payment_id = (cuerpo.get('data') or {}).get('id')

    if not payment_id:
        # Mercado Pago también manda notificaciones de otros tipos (ej.
        # merchant_order) que no traen un pago -- no es un error, solo no
        # hay nada que hacer con esta notificación puntual.
        return HttpResponse(status=200)

    try:
        pago = mercadopago_checkout.obtener_pago(payment_id)
    except Exception:
        logger.exception('No se pudo consultar el pago %s en el webhook de cursos', payment_id)
        return HttpResponse(status=200)

    external_reference = pago.get('external_reference')
    if not external_reference:
        return HttpResponse(status=200)

    try:
        inscripcion = InscripcionCurso.objects.get(pk=external_reference)
    except (InscripcionCurso.DoesNotExist, ValueError):
        return HttpResponse(status=200)

    if pago.get('status') == 'approved':
        _confirmar_inscripcion(inscripcion, mp_payment_id=str(pago['id']))
    elif pago.get('status') in ('rejected', 'cancelled'):
        inscripcion.estado = 'rechazado'
        inscripcion.mp_payment_id = str(pago['id'])
        inscripcion.save(update_fields=['estado', 'mp_payment_id'])

    return HttpResponse(status=200)


def _confirmar_inscripcion(inscripcion, mp_payment_id=''):
    es_nueva_aprobacion = inscripcion.marcar_aprobado(mp_payment_id=mp_payment_id)
    if es_nueva_aprobacion:
        _enviar_mails_confirmacion(inscripcion)


def _enviar_mails_confirmacion(inscripcion):
    curso = inscripcion.curso
    send_mail(
        subject=f'Confirmado: {curso.nombre}',
        message=(
            f'Hola {inscripcion.nombre},\n\n'
            f'Tu inscripción a "{curso.nombre}" quedó confirmada.\n\n'
            f'Fecha: {curso.fecha:%d/%m/%Y} a las {curso.hora:%H:%M} hs\n'
            f'Dictado por: {curso.presentador}\n\n'
            'Cualquier consulta, respondé este mail.'
        ),
        from_email=None,
        recipient_list=[inscripcion.email],
    )
    send_mail(
        subject=f'Nueva inscripción pagada: {curso.nombre}',
        message=(
            f'{inscripcion.nombre} ({inscripcion.email} / {inscripcion.whatsapp}) '
            f'se inscribió y pagó "{curso.nombre}" -- '
            f"{'Miembros Atención Psi' if inscripcion.es_red_consulta else 'público general'}, "
            f'${inscripcion.monto}.'
        ),
        from_email=None,
        recipient_list=[settings.TURNOS_BCC_EMAIL],
    )
    if curso.presentador_email:
        send_mail(
            subject=f'Nueva persona anotada en "{curso.nombre}"',
            message=(
                f'Hola,\n\n'
                f'{inscripcion.nombre} se acaba de anotar y pagar tu curso '
                f'"{curso.nombre}" ({curso.fecha:%d/%m/%Y} a las {curso.hora:%H:%M} hs).\n\n'
                f'Contacto: {inscripcion.email} / {inscripcion.whatsapp}\n\n'
                'Cualquier consulta, respondé este mail.'
            ),
            from_email=None,
            recipient_list=[curso.presentador_email],
        )
