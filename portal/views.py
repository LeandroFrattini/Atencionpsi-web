from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.utils import timezone

from .decorators import psicologo_requerido
from .forms import PacienteForm, TurnoForm
from .models import Paciente, Turno
from .scoping import get_paciente_or_404, get_turno_or_404


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
    ahora = timezone.now()
    proximos_turnos = (
        Turno.objects.filter(psicologo=psico, fecha_hora__gte=ahora)
        .exclude(estado='cancelado')
        .order_by('fecha_hora')[:15]
    )
    return render(request, 'portal/dashboard.html', {
        'psico': psico,
        'proximos_turnos': proximos_turnos,
    })


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
