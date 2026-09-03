import datetime
import logging
import random
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Psicologo, Modalidad, Publico, Orientacion, ClickWhatsApp, Ciudad
from .bot_detector import es_bot

from portal.disponibilidad import fecha_larga, fechas_horizonte, slot_disponible, slots_para_fecha
from portal.forms import ReservaPublicaForm
from portal.models import Paciente, Turno
from portal.notificaciones import enviar_aviso_nuevo_turno

logger = logging.getLogger(__name__)


# --- VISTA DE INICIO ---
def inicio(request):
    total_profesionales = Psicologo.objects.filter(activo=True).count()
    # Ciudades únicas no vacías (excluyendo "Online")
    total_ciudades = Ciudad.objects.filter(psicologo__isnull=False).distinct().count()

    return render(request, 'index.html', {
        'total_profesionales': total_profesionales,
        'total_ciudades': total_ciudades,
        'profesionales_home': _seis_para_home(),
    })


def _seis_para_home():
    """
    Siempre 6 profesionales para la home, siempre en orden aleatorio.
    Los marcados como destacado entran primero (si hay más de 6 destacados,
    se eligen 6 al azar entre ellos); el resto de los lugares se completa
    al azar con el resto de los profesionales activos.
    """
    activos = list(Psicologo.objects.filter(activo=True))
    destacados = [p for p in activos if p.destacado]
    random.shuffle(destacados)
    elegidos = destacados[:6]

    if len(elegidos) < 6:
        ids_usados = {p.id for p in elegidos}
        resto = [p for p in activos if p.id not in ids_usados]
        random.shuffle(resto)
        elegidos += resto[:6 - len(elegidos)]

    random.shuffle(elegidos)
    return elegidos


# --- VISTA DEL BUSCADOR ---
def buscador(request):
    modalidad_id = request.GET.get('modalidad')
    dirigido_a_id = request.GET.get('dirigido_a')
    orientacion_id = request.GET.get('orientacion')
    ciudad = request.GET.get('ciudad')
    nombre_q = request.GET.get('nombre', '').strip()

    queryset = Psicologo.objects.filter(activo=True)

    if nombre_q:
        # nombre guarda el nombre completo (ej: "Lic. Oriana Casazza") --
        # no hay campo apellido separado, así que un texto libre alcanza
        # para buscar por nombre o apellido igual.
        queryset = queryset.filter(nombre__icontains=nombre_q)

    if modalidad_id:
        queryset = queryset.filter(modalidades__id=modalidad_id)

    if dirigido_a_id:
        queryset = queryset.filter(destinatarios__id=dirigido_a_id)

    if orientacion_id:
        queryset = queryset.filter(orientaciones__id=orientacion_id)

    if ciudad:
        # Incluir profesionales de esa ciudad Y de todos sus barrios
        from django.db.models import Q
        queryset = queryset.filter(
            Q(ciudades__id=ciudad) | Q(ciudades__ciudad_padre__id=ciudad)
        )

    # Destacados primero, el resto en orden aleatorio
    destacados = list(queryset.filter(destacado=True).distinct())
    comunes = list(queryset.filter(destacado=False).distinct())
    random.shuffle(comunes)
    lista_final = destacados + comunes

    # Armar lista jerárquica para el dropdown
    ciudades_padres = []
    for ciudad in Ciudad.objects.filter(ciudad_padre__isnull=True):
        ciudad.barrios_list = list(ciudad.barrios.all())
        ciudades_padres.append(ciudad)

    return render(request, 'buscador.html', {
        'psicologos': lista_final,
        'modalidades_list': Modalidad.objects.all(),
        'destinatarios_list': Publico.objects.all(),
        'orientaciones_list': Orientacion.objects.all(),
        'ciudades_padres': ciudades_padres,
        'nombre_q': nombre_q,
    })


# --- VISTA DE PERFIL ---
def detalle_psicologo(request, slug):
    psicologo = get_object_or_404(Psicologo, slug=slug, activo=True)
    return render(request, 'perfil.html', {'p': psicologo})


# --- TURNERO PÚBLICO ---
def reservar_turno(request, slug):
    """
    Paso 1: calendario con los horarios libres de esta semana y la próxima
    (3 días visibles por vez, con "grupo" para paginar). Paso 2 (elegir un
    horario libre vía ?fecha=&hora=): formulario de datos del paciente.
    La disponibilidad sale de DisponibilidadSemanal/DiaNoAtiende -- ver
    portal/disponibilidad.py.
    """
    psicologo = get_object_or_404(Psicologo, slug=slug, activo=True)

    try:
        grupo = int(request.GET.get('grupo', 0))
    except ValueError:
        grupo = 0
    grupo = max(0, min(3, grupo))

    fechas = fechas_horizonte()
    dias_visibles = fechas[grupo * 3: grupo * 3 + 3]
    dias = [{'fecha': fecha, 'slots': slots_para_fecha(psicologo, fecha)} for fecha in dias_visibles]

    elegido = None
    form = None
    fecha_str, hora_str = request.GET.get('fecha'), request.GET.get('hora')
    if fecha_str and hora_str:
        try:
            fecha_e = datetime.date.fromisoformat(fecha_str)
            hora_e = datetime.time.fromisoformat(hora_str)
        except ValueError:
            fecha_e = hora_e = None
        if fecha_e and hora_e:
            disponible, modalidad = slot_disponible(psicologo, fecha_e, hora_e)
            if disponible:
                elegido = {
                    'fecha': fecha_e,
                    'hora': hora_e,
                    'modalidad': modalidad,
                    'hora_hasta': _sumar_minutos(hora_e, fecha_e, psicologo.duracion_turno_min),
                    'fecha_larga': fecha_larga(fecha_e),
                }
                form = ReservaPublicaForm()
            else:
                messages.error(request, 'Ese horario ya no está disponible, elegí otro.')

    return render(request, 'reservar.html', {
        'p': psicologo, 'dias': dias, 'grupo': grupo,
        'elegido': elegido, 'form': form,
    })


def _sumar_minutos(hora, fecha, minutos):
    return (datetime.datetime.combine(fecha, hora) + datetime.timedelta(minutes=minutos)).time()


@require_POST
def reservar_confirmar(request, slug):
    psicologo = get_object_or_404(Psicologo, slug=slug, activo=True)
    fecha_str, hora_str = request.POST.get('fecha'), request.POST.get('hora')
    try:
        fecha = datetime.date.fromisoformat(fecha_str)
        hora = datetime.time.fromisoformat(hora_str)
    except (TypeError, ValueError):
        messages.error(request, 'Hubo un problema con el horario elegido. Probá de nuevo.')
        return redirect('reservar_turno', slug=slug)

    disponible, modalidad = slot_disponible(psicologo, fecha, hora)
    if not disponible:
        messages.error(request, 'Uy, justo se ocupó ese horario. Elegí otro.')
        return redirect('reservar_turno', slug=slug)

    form = ReservaPublicaForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            fecha_hora = timezone.make_aware(datetime.datetime.combine(fecha, hora))
            # último chequeo dentro de la transacción, por si dos personas
            # reservan el mismo horario casi al mismo tiempo
            ya_ocupado = Turno.objects.filter(
                psicologo=psicologo, fecha_hora=fecha_hora
            ).exclude(estado='cancelado').exists()
            if ya_ocupado:
                messages.error(request, 'Uy, justo se ocupó ese horario. Elegí otro.')
                return redirect('reservar_turno', slug=slug)

            paciente, _creado = Paciente.objects.get_or_create(
                psicologo=psicologo, email=form.cleaned_data['email'],
                defaults={
                    'nombre': form.cleaned_data['nombre'],
                    'apellido': form.cleaned_data['apellido'],
                    'telefono': form.cleaned_data['telefono'],
                    'fecha_nacimiento': form.cleaned_data['fecha_nacimiento'],
                },
            )
            turno = Turno.objects.create(
                psicologo=psicologo, paciente=paciente, fecha_hora=fecha_hora,
                modalidad=modalidad, origen='publico',
            )
        # El turno ya quedó guardado (arriba, en su propia transacción) --
        # si el mail de aviso falla (Brevo caído, red, lo que sea), eso NO
        # tiene que tirar abajo la confirmación: el paciente ya reservó de
        # verdad y tiene que ver la pantalla de éxito igual. Se loguea el
        # error para poder darse cuenta y, si hace falta, avisar a mano.
        try:
            enviar_aviso_nuevo_turno(turno)
        except Exception:
            logger.exception(
                'No se pudo enviar el mail de aviso del turno %s (psicólogo %s, paciente %s)',
                turno.pk, psicologo.nombre, paciente.pk,
            )
        return render(request, 'reserva_confirmada.html', {'p': psicologo, 'turno': turno})

    elegido = {
        'fecha': fecha, 'hora': hora, 'modalidad': modalidad,
        'hora_hasta': _sumar_minutos(hora, fecha, psicologo.duracion_turno_min),
        'fecha_larga': fecha_larga(fecha),
    }
    return render(request, 'reservar.html', {
        'p': psicologo, 'dias': [], 'grupo': 0, 'elegido': elegido, 'form': form,
    })


# --- REDIRECT WHATSAPP (fallback por compatibilidad, YA NO cuenta clicks) ---
def wa_redirect(request, slug):
    """
    Se mantiene solo por si hay links viejos indexados o compartidos apuntando acá.
    El conteo de clicks real se hace en registrar_click_whatsapp (ver abajo),
    que se dispara únicamente por JS ante un click humano real. Los templates
    actuales ya no usan esta vista para el botón de WhatsApp.
    """
    psicologo = get_object_or_404(Psicologo, slug=slug)
    wa_url = (
        f"https://wa.me/{psicologo.whatsapp}"
        "?text=Hola,%20te%20escribo%20desde%20Atenci%C3%B3n%20Psi,"
        "%20me%20gustar%C3%ADa%20coordinar%20un%20turno%20con%20vos!"
    )
    return redirect(wa_url)


# --- REGISTRO DE CLICK REAL (llamado por JS ante un click humano) ---
@require_POST
def registrar_click_whatsapp(request, slug):
    """
    Registra un click REAL en el botón de WhatsApp.
    Se llama solo desde JavaScript, disparado por el evento 'click' del navegador.
    Un bot que solo lee el HTML (Google, previews de WhatsApp/Facebook, scrapers,
    etc.) nunca ejecuta JS ni dispara clicks, así que nunca llega acá.
    Además se filtra por User-Agent como capa extra de seguridad.
    """
    if es_bot(request):
        return JsonResponse({'ok': False})

    psicologo = get_object_or_404(Psicologo, slug=slug)
    try:
        hoy = timezone.localdate()
        with transaction.atomic():
            click, created = ClickWhatsApp.objects.get_or_create(
                fecha=hoy,
                psicologo=psicologo,
                defaults={'cantidad': 1}
            )
            if not created:
                ClickWhatsApp.objects.filter(pk=click.pk).update(cantidad=click.cantidad + 1)
    except Exception:
        pass

    return JsonResponse({'ok': True})


# --- VISTA ÚNETE ---
def unete(request):
    return render(request, 'unete.html')


def sobre_nosotros(request):
    return render(request, 'sobre_nosotros.html')


def faq(request):
    return render(request, 'faq.html')


def formacion(request):
    return render(request, 'formacion.html')
