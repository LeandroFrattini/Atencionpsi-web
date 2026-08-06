"""
Cálculo de horarios reservables del turnero público a partir de la
plantilla semanal (DisponibilidadSemanal) de cada psicólogo, descontando
los días que no atiende (DiaNoAtiende) y los turnos que ya están ocupados
ese día puntual.
"""
import datetime

from django.utils import timezone

from .models import DiaNoAtiende, Turno

HORIZONTE_SEMANAS = 2  # esta semana + la próxima, nada más allá

NOMBRES_DIA = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
NOMBRES_MES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]


def fecha_larga(fecha):
    return f'{NOMBRES_DIA[fecha.weekday()]} {fecha.day} de {NOMBRES_MES[fecha.month - 1]}'


def fechas_horizonte(hoy=None):
    """Lunes a sábado de esta semana y de la próxima (nunca domingo)."""
    hoy = hoy or timezone.localdate()
    lunes = hoy - datetime.timedelta(days=hoy.weekday())
    return [
        lunes + datetime.timedelta(weeks=semana, days=dia)
        for semana in range(HORIZONTE_SEMANAS)
        for dia in range(6)
    ]


def esta_en_dia_no_atiende(psico, fecha):
    return DiaNoAtiende.objects.filter(
        psicologo=psico, fecha_desde__lte=fecha, fecha_hasta__gte=fecha
    ).exists()


def _horas_ocupadas(psico, fecha):
    """
    Horas (hora local, sin segundos) con un turno ya cargado ese día para
    ese psicólogo. Se trae un rango de un día antes/después y se filtra por
    fecha local en Python -- así se evita el mismo problema de huso horario
    que ya se resuelve así en portal/views.py:dashboard (un turno de noche
    en UTC puede caer en el día siguiente/anterior si se compara en la DB).
    """
    desde = fecha - datetime.timedelta(days=1)
    hasta = fecha + datetime.timedelta(days=1)
    turnos = Turno.objects.filter(
        psicologo=psico, fecha_hora__date__range=(desde, hasta)
    ).exclude(estado='cancelado')
    ocupadas = set()
    for turno in turnos:
        local = timezone.localtime(turno.fecha_hora)
        if local.date() == fecha:
            ocupadas.add(local.time().replace(second=0, microsecond=0))
    return ocupadas


def slots_para_fecha(psico, fecha, duracion_min=None):
    """
    Devuelve la lista de horarios de ese día, partidos según la duración de
    turno del psicólogo: [{'hora': time, 'modalidad': 'presencial'|'virtual',
    'tomado': bool}, ...]. Vacía si el día cae en un período de "no atiende"
    o es domingo.
    """
    if fecha.weekday() == 6 or esta_en_dia_no_atiende(psico, fecha):
        return []

    duracion_min = duracion_min or psico.duracion_turno_min
    paso = datetime.timedelta(minutes=duracion_min)
    ocupadas = _horas_ocupadas(psico, fecha)

    slots = []
    bloques = psico.disponibilidad_semanal.filter(dia_semana=fecha.weekday()).order_by('hora_desde')
    for bloque in bloques:
        cursor = datetime.datetime.combine(fecha, bloque.hora_desde)
        fin = datetime.datetime.combine(fecha, bloque.hora_hasta)
        while cursor + paso <= fin:
            hora = cursor.time()
            slots.append({'hora': hora, 'modalidad': bloque.modalidad, 'tomado': hora in ocupadas})
            cursor += paso
    slots.sort(key=lambda s: s['hora'])
    return slots


def slot_disponible(psico, fecha, hora, duracion_min=None):
    """Re-chequeo puntual (usado al confirmar una reserva) de que ese horario sigue libre."""
    for slot in slots_para_fecha(psico, fecha, duracion_min=duracion_min):
        if slot['hora'] == hora:
            return not slot['tomado'], slot['modalidad']
    return False, None
