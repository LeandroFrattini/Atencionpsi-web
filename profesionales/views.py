import random
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Psicologo, Modalidad, Publico, ClickWhatsApp, Ciudad
from .bot_detector import es_bot


# --- VISTA DE INICIO ---
def inicio(request):
    total_profesionales = Psicologo.objects.count()
    # Ciudades únicas no vacías (excluyendo "Online")
    total_ciudades = Ciudad.objects.filter(psicologo__isnull=False).distinct().count()

    return render(request, 'index.html', {
        'total_profesionales': total_profesionales,
        'total_ciudades': total_ciudades,
    })


# --- VISTA DEL BUSCADOR ---
def buscador(request):
    modalidad_id = request.GET.get('modalidad')
    dirigido_a_id = request.GET.get('dirigido_a')
    ciudad = request.GET.get('ciudad')

    queryset = Psicologo.objects.all()

    if modalidad_id:
        queryset = queryset.filter(modalidades__id=modalidad_id)

    if dirigido_a_id:
        queryset = queryset.filter(destinatarios__id=dirigido_a_id)

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
        'ciudades_padres': ciudades_padres,
    })


# --- VISTA DE PERFIL ---
def detalle_psicologo(request, slug):
    psicologo = get_object_or_404(Psicologo, slug=slug)
    return render(request, 'perfil.html', {'p': psicologo})


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
