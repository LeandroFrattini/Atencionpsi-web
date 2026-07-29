import calendar
import datetime

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import psicologo_requerido
from .forms import PacienteForm, TurnoForm
from .models import Paciente, Turno
from .scoping import get_paciente_or_404, get_turno_or_404

NOMBRES_DIA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
NOMBRES_MES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]


@psicologo_requerido(permitir_cambio_pendiente=True)
def cambiar_password(request, psico):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # no lo desloguea al cambiarla
            psico.debe_cambiar_password = False
            psico.save(update_fields=['debe_cambiar_password'])
            messages.success(request, 'Contraseña actualizada correctamente.')
            return redirect('portal_dashboard')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'portal/cambiar_password.html', {
        'psico': psico, 'form': form, 'obligatorio': psico.debe_cambiar_password,
    })


@psicologo_requerido
def dashboard(request, psico):
    hoy = timezone.localdate()
    try:
        offset = int(request.GET.get('semana', 0))
    except ValueError:
        offset = 0

    lunes = hoy - datetime.timedelta(days=hoy.weekday()) + datetime.timedelta(weeks=offset)
    domingo = lunes + datetime.timedelta(days=6)

    turnos_semana = (
        Turno.objects.filter(psicologo=psico, fecha_hora__date__range=(lunes, domingo))
        .select_related('paciente')
        .order_by('fecha_hora')
    )
    turnos_por_dia = {}
    for turno in turnos_semana:
        # fecha_hora llega en UTC desde la base; hay que pasarla a hora local
        # antes de sacar el día, si no un turno de noche puede caer en el
        # cuadrado del día siguiente.
        turnos_por_dia.setdefault(timezone.localtime(turno.fecha_hora).date(), []).append(turno)

    dia_default = None
    dias = []
    for i in range(7):
        fecha = lunes + datetime.timedelta(days=i)
        turnos_dia = turnos_por_dia.get(fecha, [])
        es_hoy = fecha == hoy
        dias.append({
            'fecha': fecha,
            'nombre': NOMBRES_DIA[i][:3],
            'nombre_largo': NOMBRES_DIA[i],
            'es_hoy': es_hoy,
            'turnos': turnos_dia,
            'count': len([t for t in turnos_dia if t.estado != 'cancelado']),
        })
        if es_hoy:
            dia_default = i

    if dia_default is None:
        # otra semana: abrimos el primer día con turnos, o el lunes si no hay ninguno
        dia_default = next((i for i, d in enumerate(dias) if d['turnos']), 0)

    ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    mes_inicio = hoy.replace(day=1)
    mes_fin = hoy.replace(day=ultimo_dia_mes)
    turnos_mes = Turno.objects.filter(psicologo=psico, fecha_hora__date__range=(mes_inicio, mes_fin))
    stats = {
        'atendidos': turnos_mes.filter(estado='realizado').count(),
        'cancelados': turnos_mes.filter(estado='cancelado').count(),
        'sin_cobrar': turnos_mes.filter(estado='realizado', pagado=False).count(),
    }
    mes_label = f'{NOMBRES_MES[hoy.month - 1]} {hoy.year}'

    return render(request, 'portal/dashboard.html', {
        'psico': psico,
        'dias': dias,
        'lunes': lunes,
        'domingo': domingo,
        'semana_offset': offset,
        'dia_default': dia_default,
        'stats': stats,
        'mes_label': mes_label,
    })


@psicologo_requerido
@require_POST
def turno_marcar_realizado(request, psico, pk):
    turno = get_turno_or_404(psico, pk)
    turno.estado = 'realizado'
    turno.pagado = request.POST.get('pagado') == '1'
    notas = request.POST.get('notas_sesion', '').strip()
    if notas:
        turno.notas_sesion = notas
    turno.save(update_fields=['estado', 'notas_sesion', 'pagado', 'actualizado_en'])
    if turno.pagado:
        messages.success(request, f'Turno de {turno.paciente} marcado como realizado y pagado.')
    else:
        messages.warning(request, f'Turno de {turno.paciente} realizado. Todavía no pagó — quedó marcado para cobrar.')
    return redirect(request.POST.get('next') or 'portal_dashboard')


@psicologo_requerido
@require_POST
def turno_marcar_pagado(request, psico, pk):
    turno = get_turno_or_404(psico, pk)
    turno.pagado = True
    turno.save(update_fields=['pagado', 'actualizado_en'])
    messages.success(request, f'Turno de {turno.paciente} marcado como pagado.')
    return redirect(request.POST.get('next') or 'portal_dashboard')


@psicologo_requerido
@require_POST
def turno_reagendar_rapido(request, psico, pk):
    turno = get_turno_or_404(psico, pk)
    turno.fecha_hora = turno.fecha_hora + datetime.timedelta(weeks=1)
    turno.estado = 'agendado'
    turno.reagendado = True
    turno.save(update_fields=['fecha_hora', 'estado', 'reagendado', 'actualizado_en'])
    nueva_fecha_local = timezone.localtime(turno.fecha_hora)
    messages.success(request, f'Turno de {turno.paciente} reagendado para el {nueva_fecha_local:%d/%m %H:%M}.')
    return redirect(request.POST.get('next') or 'portal_dashboard')


@psicologo_requerido
def pacientes_lista(request, psico):
    pacientes = Paciente.objects.filter(psicologo=psico)
    return render(request, 'portal/pacientes_list.html', {
        'psico': psico,
        'pacientes': pacientes,
    })


@psicologo_requerido
def paciente_nuevo(request, psico):
    if request.method == 'POST':
        form = PacienteForm(request.POST)
        if form.is_valid():
            paciente = form.save(commit=False)
            paciente.psicologo = psico
            paciente.save()
            messages.success(request, 'Paciente creado correctamente.')
            return redirect('portal_paciente_detalle', pk=paciente.pk)
    else:
        form = PacienteForm()
    return render(request, 'portal/paciente_form.html', {
        'psico': psico, 'form': form, 'modo': 'nuevo',
    })


@psicologo_requerido
def paciente_detalle(request, psico, pk):
    paciente = get_paciente_or_404(psico, pk)
    turnos = paciente.turnos.all()
    return render(request, 'portal/paciente_detalle.html', {
        'psico': psico, 'paciente': paciente, 'turnos': turnos,
    })


@psicologo_requerido
def paciente_editar(request, psico, pk):
    paciente = get_paciente_or_404(psico, pk)
    if request.method == 'POST':
        form = PacienteForm(request.POST, instance=paciente)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paciente actualizado.')
            return redirect('portal_paciente_detalle', pk=paciente.pk)
    else:
        form = PacienteForm(instance=paciente)
    return render(request, 'portal/paciente_form.html', {
        'psico': psico, 'form': form, 'modo': 'editar', 'paciente': paciente,
    })


@psicologo_requerido
def turno_nuevo(request, psico):
    if request.method == 'POST':
        form = TurnoForm(request.POST, psico=psico)
        if form.is_valid():
            turno = form.save(commit=False)
            turno.psicologo = psico
            turno.save()
            messages.success(request, 'Turno agendado.')
            return redirect('portal_paciente_detalle', pk=turno.paciente_id)
    else:
        initial = {}
        paciente_id = request.GET.get('paciente')
        if paciente_id:
            # el paciente preseleccionado también se valida contra el propio psicólogo
            paciente = Paciente.objects.filter(pk=paciente_id, psicologo=psico).first()
            if paciente:
                initial['paciente'] = paciente
        form = TurnoForm(psico=psico, initial=initial)
    return render(request, 'portal/turno_form.html', {
        'psico': psico, 'form': form, 'modo': 'nuevo',
    })


@psicologo_requerido
def turno_editar(request, psico, pk):
    turno = get_turno_or_404(psico, pk)
    fecha_original = turno.fecha_hora
    if request.method == 'POST':
        form = TurnoForm(request.POST, instance=turno, psico=psico)
        if form.is_valid():
            turno = form.save(commit=False)
            if turno.fecha_hora != fecha_original:
                turno.reagendado = True
            turno.save()
            messages.success(request, 'Turno actualizado.')
            return redirect('portal_paciente_detalle', pk=turno.paciente_id)
    else:
        form = TurnoForm(instance=turno, psico=psico)
    return render(request, 'portal/turno_form.html', {
        'psico': psico, 'form': form, 'modo': 'editar', 'turno': turno,
    })
