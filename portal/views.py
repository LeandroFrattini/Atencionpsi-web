import calendar
import datetime

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from profesionales.admin import CrearAccesoPortalForm
from profesionales.models import Psicologo

from .decorators import psicologo_requerido, superuser_requerido
from .forms import PacienteForm, TurnoForm
from .models import IngresoPortal, Paciente, Turno
from .scoping import get_paciente_or_404, get_turno_or_404

NOMBRES_DIA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
NOMBRES_MES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

# Rango horario por defecto de la grilla tipo Google Calendar; si hay un
# turno fuera de este rango, la grilla de ese día se estira para incluirlo.
HORA_INICIO_DEFECTO = 6
HORA_FIN_DEFECTO = 24
DURACION_TURNO_MIN = 50
MINUTOS_SNAP = 15


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
    sabado = lunes + datetime.timedelta(days=5)  # la agenda es de lunes a sábado, domingo no se trabaja

    turnos_semana = (
        Turno.objects.filter(psicologo=psico, fecha_hora__date__range=(lunes, sabado))
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
    for i in range(6):
        fecha = lunes + datetime.timedelta(days=i)
        turnos_dia = turnos_por_dia.get(fecha, [])
        es_hoy = fecha == hoy

        horas_turnos = [timezone.localtime(t.fecha_hora).hour for t in turnos_dia]
        hora_inicio = min([HORA_INICIO_DEFECTO] + horas_turnos)
        hora_fin = max([HORA_FIN_DEFECTO] + [h + 1 for h in horas_turnos])
        total_min = (hora_fin - hora_inicio) * 60

        for turno in turnos_dia:
            local = timezone.localtime(turno.fecha_hora)
            offset_min = (local.hour - hora_inicio) * 60 + local.minute
            # Atributos de solo lectura para posicionar el evento en la
            # grilla (van directo a un style="" inline, por eso se arman
            # como string con punto decimal: con LANGUAGE_CODE=es-ar,
            # Django renderiza los floats con coma ("7,69%"), lo que
            # rompe el CSS y el evento queda invisible sin ningún error).
            turno.top_pct = f'{offset_min / total_min * 100:.2f}'
            turno.height_pct = f'{min(DURACION_TURNO_MIN, total_min - offset_min) / total_min * 100:.2f}'

        lineas = [
            {'hora': h % 24, 'top_pct': f'{(h - hora_inicio) / (hora_fin - hora_inicio) * 100:.2f}'}
            for h in range(hora_inicio, hora_fin + 1)
        ]

        dias.append({
            'fecha': fecha,
            'nombre': NOMBRES_DIA[i][:3],
            'nombre_largo': NOMBRES_DIA[i],
            'es_hoy': es_hoy,
            'turnos': turnos_dia,
            'count': len([t for t in turnos_dia if t.estado != 'cancelado']),
            'hora_inicio': hora_inicio,
            'hora_fin': hora_fin,
            'n_horas': hora_fin - hora_inicio,
            'lineas': lineas,
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
        'sabado': sabado,
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
    """
    "Reagendar" no mueve el turno original: crea uno nuevo una semana
    después, a la misma hora, para el mismo paciente. Así se puede usar
    sobre un turno ya realizado (ej. el paciente vino hoy a las 17hs y a
    la noche se arma la sesión de la semana que viene) sin perder el
    registro de lo que pasó hoy.
    """
    turno = get_turno_or_404(psico, pk)
    nueva_fecha = turno.fecha_hora + datetime.timedelta(weeks=1)
    nuevo_turno = Turno.objects.create(
        psicologo=psico,
        paciente=turno.paciente,
        fecha_hora=nueva_fecha,
        estado='agendado',
        reagendado=True,
    )
    nueva_fecha_local = timezone.localtime(nuevo_turno.fecha_hora)
    messages.success(
        request,
        f'Se creó un turno para {turno.paciente} el {nueva_fecha_local:%d/%m} a las {nueva_fecha_local:%H:%M}.',
    )
    return redirect(request.POST.get('next') or 'portal_dashboard')


@psicologo_requerido
@require_POST
def turno_mover(request, psico, pk):
    """
    Arrastrar un turno a otro horario (dentro del mismo día) o a otro día
    (arrastrándolo hasta el selector de días de la semana). El parámetro
    `fecha` es opcional: si no viene, se mantiene el día original.
    """
    turno = get_turno_or_404(psico, pk)
    try:
        hora = int(request.POST.get('hora'))
        minuto = int(request.POST.get('minuto'))
    except (TypeError, ValueError):
        return redirect(request.POST.get('next') or 'portal_dashboard')

    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        return redirect(request.POST.get('next') or 'portal_dashboard')

    local = timezone.localtime(turno.fecha_hora)
    fecha_str = (request.POST.get('fecha') or '').strip()
    if fecha_str:
        try:
            nueva_fecha = datetime.date.fromisoformat(fecha_str)
        except ValueError:
            return redirect(request.POST.get('next') or 'portal_dashboard')
    else:
        nueva_fecha = local.date()

    turno.fecha_hora = local.replace(
        year=nueva_fecha.year, month=nueva_fecha.month, day=nueva_fecha.day,
        hour=hora, minute=minuto, second=0, microsecond=0,
    )
    turno.reagendado = True
    turno.save(update_fields=['fecha_hora', 'reagendado', 'actualizado_en'])
    messages.success(
        request,
        f'Turno de {turno.paciente} movido al {nueva_fecha:%d/%m} a las {hora:02d}:{minuto:02d}.',
    )
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


@superuser_requerido
def admin_dashboard(request):
    """
    Panel general para la cuenta de la dueña del sitio (superuser sin
    Psicologo asociado): estadísticas GENERALES nada más (cantidad de
    pacientes cargados en toda la red, cantidad de profesionales con
    agenda activa) y la lista completa para dar de alta/baja quién
    aparece en el buscador público.

    A propósito NO se muestran acá los datos de turnos por profesional
    (atendidos/cancelados/sin cobrar) -- eso es información privada de
    cada psicólogo con sus pacientes, no algo que la dueña del sitio
    tenga que ver agregado.
    """
    psicologos = Psicologo.objects.all().order_by('-activo', 'nombre')
    total_psicologos = len(psicologos)
    total_con_agenda = sum(1 for p in psicologos if p.usuario_id)

    hoy = timezone.localdate()
    ingresos_hoy = IngresoPortal.objects.filter(fecha=hoy).count()

    # Últimos 7 días completos (con 0 en los días sin ingresos, para que se
    # note si un día nadie entró en vez de que ese día directamente falte).
    inicio_semana = hoy - datetime.timedelta(days=6)
    conteo_por_fecha = {
        fila['fecha']: fila['cantidad']
        for fila in (
            IngresoPortal.objects.filter(fecha__gte=inicio_semana)
            .values('fecha')
            .annotate(cantidad=Count('id'))
        )
    }
    ultimos_7_dias = [
        {
            'fecha': fecha,
            'nombre_dia': NOMBRES_DIA[fecha.weekday()][:3],
            'cantidad': conteo_por_fecha.get(fecha, 0),
            'es_hoy': fecha == hoy,
        }
        for fecha in (inicio_semana + datetime.timedelta(days=i) for i in range(7))
    ]

    stats = {
        'total_pacientes': Paciente.objects.count(),
        'total_con_agenda': total_con_agenda,
        'ingresos_hoy': ingresos_hoy,
    }

    return render(request, 'portal/admin_dashboard.html', {
        'stats': stats,
        'psicologos': psicologos,
        'total_activos': sum(1 for p in psicologos if p.activo),
        'total_psicologos': total_psicologos,
        'ultimos_7_dias': ultimos_7_dias,
    })


@superuser_requerido
@require_POST
def psicologo_toggle_activo(request, pk):
    psico = get_object_or_404(Psicologo, pk=pk)
    psico.activo = not psico.activo
    psico.save(update_fields=['activo'])
    if psico.activo:
        messages.success(request, f'{psico.nombre} vuelve a aparecer en el buscador.')
    else:
        messages.warning(request, f'{psico.nombre} dado de baja: ya no aparece en el buscador.')
    return redirect('portal_admin_dashboard')


@superuser_requerido
def psicologo_crear_acceso(request, pk):
    """
    Mismo formulario y misma lógica que la acción del admin de Django
    (crear_acceso_portal_action) para no duplicar reglas -- pero acá, sin
    tener que salir del panel del portal.
    """
    psico = get_object_or_404(Psicologo, pk=pk)

    if request.method == 'POST':
        form = CrearAccesoPortalForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password_inicial = form.cleaned_data['password_inicial']

            ya_existe = User.objects.filter(username__iexact=email)
            if psico.usuario_id:
                ya_existe = ya_existe.exclude(pk=psico.usuario_id)

            if ya_existe.exists():
                form.add_error('email', 'Ya hay un usuario con ese email.')
            else:
                if psico.usuario:
                    user = psico.usuario
                    user.username = email
                    user.email = email
                else:
                    user = User(username=email, email=email)
                user.is_staff = False
                user.is_superuser = False
                user.set_password(password_inicial)
                user.save()

                psico.usuario = user
                psico.debe_cambiar_password = True
                psico.save(update_fields=['usuario', 'debe_cambiar_password'])

                messages.success(
                    request,
                    f'Acceso creado para {psico.nombre}. Usuario: {email} — contraseña inicial: {password_inicial}. '
                    f'Pasale estos datos; en el primer ingreso va a tener que cambiarla.',
                )
                return redirect('portal_admin_dashboard')
    else:
        form = CrearAccesoPortalForm(initial={'password_inicial': psico.whatsapp_limpio()})

    return render(request, 'portal/psicologo_acceso_form.html', {'psico': psico, 'form': form})


@superuser_requerido
@require_POST
def psicologo_blanquear_password(request, pk):
    """Para cuando un profesional se olvida la clave: la resetea a su WhatsApp y lo obliga a cambiarla de nuevo."""
    psico = get_object_or_404(Psicologo, pk=pk)
    if not psico.usuario_id:
        messages.error(request, f'{psico.nombre} todavía no tiene acceso al portal creado.')
        return redirect('portal_admin_dashboard')

    nueva_password = psico.whatsapp_limpio()
    psico.usuario.set_password(nueva_password)
    psico.usuario.save(update_fields=['password'])
    psico.debe_cambiar_password = True
    psico.save(update_fields=['debe_cambiar_password'])
    messages.success(
        request,
        f'Contraseña de {psico.nombre} reseteada a su WhatsApp ({nueva_password}). '
        f'Va a tener que cambiarla en el próximo ingreso.',
    )
    return redirect('portal_admin_dashboard')
