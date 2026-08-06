"""
Aviso por mail al profesional cuando un paciente reserva un turno desde el
turnero público. Solo se dispara para turnos con origen='publico' -- los
que el profesional carga a mano en "Nuevo turno" no mandan nada (ver
Turno.origen en portal/models.py).
"""
import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .disponibilidad import fecha_larga as _fecha_larga


def enviar_con_contexto(destinatario_email, contexto):
    """Punto de entrada compartido por el aviso real y por el comando test_email."""
    asunto = f"Nuevo turno: {contexto['paciente_nombre']} — {contexto['fecha_corta']} · Atención Psi"
    texto = render_to_string('portal/email_nuevo_turno.txt', contexto)
    html = render_to_string('portal/email_nuevo_turno.html', contexto)
    mail = EmailMultiAlternatives(
        subject=asunto,
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario_email],
        bcc=[settings.TURNOS_BCC_EMAIL] if settings.TURNOS_BCC_EMAIL else [],
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
    """Se llama después de crear un Turno con origen='publico'. Si el psicólogo
    no tiene mail de acceso al portal, no hay a quién avisarle y no hace nada."""
    psico = turno.psicologo
    if not (psico.usuario_id and psico.usuario.email):
        return

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
    enviar_con_contexto(psico.usuario.email, contexto)
