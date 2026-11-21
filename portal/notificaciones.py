"""
Aviso por mail al profesional cuando un paciente reserva un turno desde el
turnero público. Solo se dispara para turnos con origen='publico' -- los
que el profesional carga a mano en "Nuevo turno" no mandan nada (ver
Turno.origen en portal/models.py).
"""
import datetime
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .disponibilidad import fecha_larga as _fecha_larga

logger = logging.getLogger(__name__)


def enviar_con_contexto(destinatario_email, contexto, prefijo_asunto=''):
    """Punto de entrada compartido por el aviso real, el comando test_email y el botón de prueba del admin."""
    asunto = (
        f"{prefijo_asunto}{contexto['psicologo_nombre']} - Nuevo turno - {contexto['paciente_nombre']} - "
        f"{contexto['fecha_corta']} {contexto['hora_desde']}hs - Atención Psi"
    )
    texto = render_to_string('portal/email_nuevo_turno.txt', contexto)
    html = render_to_string('portal/email_nuevo_turno.html', contexto)
    mail = EmailMultiAlternatives(
        subject=asunto,
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario_email],
        # La copia interna no se repite si el destinatario ya es ella.
        bcc=[settings.TURNOS_BCC_EMAIL] if settings.TURNOS_BCC_EMAIL and destinatario_email != settings.TURNOS_BCC_EMAIL else [],
    )
    mail.attach_alternative(html, 'text/html')
    mail.send(fail_silently=False)


def contexto_de_ejemplo():
    """Datos ficticios para probar el envío sin depender de un Turno real (ver test_email)."""
    hoy = timezone.localdate()
    fecha = hoy + datetime.timedelta(days=(7 - hoy.weekday()) % 7 or 7)
    hora_desde = datetime.time(17, 0)
    hora_hasta = datetime.time(17, 45)
    return {
        'psicologo_nombre': 'Sofía Duarte',
        'paciente_nombre': 'Martina Alonso',
        'paciente_email': 'martina@mail.com',
        'paciente_telefono': '11 5555 1234',
        'paciente_fecha_nacimiento': '14/03/1996',
        'fecha_larga': _fecha_larga(fecha),
        'fecha_corta': f'{fecha.day:02d}/{fecha.month:02d}',
        'hora_desde': hora_desde.strftime('%H:%M'),
        'hora_hasta': hora_hasta.strftime('%H:%M'),
        'modalidad_label': 'Virtual',
        'es_virtual': True,
        'direccion': '',
    }


def enviar_aviso_nuevo_turno(turno):
    """Se llama después de crear un Turno con origen='publico'. Devuelve a quién se avisó:
    'profesional'; 'copia_interna' (el profesional no tiene mail de acceso al portal, así que el aviso va solo a
    TURNOS_BCC_EMAIL, para que la reserva no pase desapercibida); o None si no había a quién avisar.
    Si el envío falla, lanza la excepción (ver intentar_aviso_nuevo_turno)."""
    psico = turno.psicologo

    duracion = datetime.timedelta(minutes=psico.duracion_turno_min)
    local = timezone.localtime(turno.fecha_hora)
    hora_hasta = (datetime.datetime.combine(local.date(), local.time()) + duracion).time()

    contexto = {
        'psicologo_nombre': psico.nombre,
        'paciente_nombre': f'{turno.paciente.nombre} {turno.paciente.apellido}',
        'paciente_email': turno.paciente.email,
        'paciente_telefono': turno.paciente.telefono,
        'paciente_fecha_nacimiento': (
            turno.paciente.fecha_nacimiento.strftime('%d/%m/%Y') if turno.paciente.fecha_nacimiento else '—'
        ),
        'fecha_larga': _fecha_larga(local.date()),
        'fecha_corta': f'{local.day:02d}/{local.month:02d}',
        'hora_desde': local.strftime('%H:%M'),
        'hora_hasta': hora_hasta.strftime('%H:%M'),
        'modalidad_label': turno.get_modalidad_display(),
        'es_virtual': turno.modalidad == 'virtual',
        'direccion': psico.direccion_consultorio,
    }
    if psico.usuario_id and psico.usuario.email:
        enviar_con_contexto(psico.usuario.email, contexto)
        return 'profesional'
    logger.warning(
        'Turno %s reservado para %s, pero no tiene mail de acceso al portal cargado.', turno.pk, psico.nombre,
    )
    if settings.TURNOS_BCC_EMAIL:
        enviar_con_contexto(settings.TURNOS_BCC_EMAIL, contexto, prefijo_asunto=f'[{psico.nombre} no tiene mail cargado] ')
        return 'copia_interna'
    return None


def intentar_aviso_nuevo_turno(turno):
    """Manda el aviso y deja anotado en el turno cómo salió (se ve en el admin y permite reenviarlo). Nunca lanza:
    la reserva ya está guardada y el paciente tiene que ver su confirmación pase lo que pase. Devuelve True si
    el aviso salió."""
    from .models import Turno

    try:
        a_quien = enviar_aviso_nuevo_turno(turno)
    except Exception as e:
        logger.exception(
            'No se pudo enviar el mail de aviso del turno %s (psicólogo %s)', turno.pk, turno.psicologo.nombre,
        )
        Turno.objects.filter(pk=turno.pk).update(aviso_enviado_en=None, aviso_error=f'{type(e).__name__}: {e}'[:300])
        return False
    if a_quien == 'profesional':
        Turno.objects.filter(pk=turno.pk).update(aviso_enviado_en=timezone.now(), aviso_error='')
    elif a_quien == 'copia_interna':
        Turno.objects.filter(pk=turno.pk).update(
            aviso_enviado_en=timezone.now(),
            aviso_error='El profesional no tiene mail de acceso: el aviso salió solo a la copia interna.',
        )
    else:
        Turno.objects.filter(pk=turno.pk).update(
            aviso_enviado_en=None, aviso_error='El profesional no tiene mail de acceso y no hay copia interna: no se avisó a nadie.',
        )
    return a_quien is not None
