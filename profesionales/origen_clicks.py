"""De dónde viene cada click en el botón de WhatsApp: IP real, navegador y anuncio de Google (gclid).

El sitio corre detrás del balanceador de Render, así que la dirección "directa" (REMOTE_ADDR) es siempre una IP
interna (10.x.x.x) y no sirve para identificar a nadie. La IP del visitante viaja en un encabezado. Como no hay
forma de saber de antemano cuál usa la infraestructura, se guardan TODOS los encabezados tal cual llegaron
(`cabeceras`) y además una IP "mejor estimación" (`ip`) para poder agrupar y ordenar.
"""
import ipaddress
import logging
import random
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.utils import timezone

registro = logging.getLogger('clicks.whatsapp')

# Encabezados que ponen los proxys con la IP del visitante, del más confiable al menos.
ENCABEZADOS_IP = ('HTTP_CF_CONNECTING_IP', 'HTTP_TRUE_CLIENT_IP', 'HTTP_X_REAL_IP')
CONSERVAR_DIAS = 30   # el detalle (con IP) no se guarda para siempre


def _ip_publica(valor):
    try:
        ip = ipaddress.ip_address((valor or '').strip())
    except ValueError:
        return False
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_unspecified)


def ip_real(request):
    """Mejor estimación de la IP del visitante (no la del proxy). Si nada sirve, devuelve REMOTE_ADDR."""
    meta = request.META
    for nombre in ENCABEZADOS_IP:
        valor = (meta.get(nombre) or '').strip()
        if _ip_publica(valor):
            return valor
    for valor in (meta.get('HTTP_X_FORWARDED_FOR') or '').split(','):
        if _ip_publica(valor):
            return valor.strip()
    return meta.get('REMOTE_ADDR', '') or ''


def cabeceras_crudas(request):
    """Los encabezados que pueden traer la IP, tal cual llegaron (para verificar a mano qué usa Render)."""
    meta = request.META
    partes = []
    for clave, nombre in (
        ('REMOTE_ADDR', 'REMOTE_ADDR'), ('HTTP_X_FORWARDED_FOR', 'X-Forwarded-For'),
        ('HTTP_CF_CONNECTING_IP', 'CF-Connecting-IP'), ('HTTP_TRUE_CLIENT_IP', 'True-Client-IP'),
        ('HTTP_X_REAL_IP', 'X-Real-IP'),
    ):
        if meta.get(clave):
            partes.append(f'{nombre}={meta[clave]}')
    return ' | '.join(partes)[:500]


def gclid_del_referer(referer):
    """El identificador del click en el anuncio de Google (gclid/gbraid/wbraid) que trae la página de origen.
    Cada click en un anuncio genera uno distinto: si el mismo aparece en muchos clicks, es una sola visita."""
    try:
        consulta = parse_qs(urlparse(referer or '').query)
    except ValueError:
        return ''
    for clave in ('gclid', 'gbraid', 'wbraid'):
        if consulta.get(clave):
            return consulta[clave][0][:120]
    return ''


def purgar_antiguos():
    from .models import ClickWhatsAppDetalle
    corte = timezone.now() - timedelta(days=CONSERVAR_DIAS)
    return ClickWhatsAppDetalle.objects.filter(creado__lt=corte).delete()[0]


def registrar_click(request, psicologo):
    """Guarda el detalle de un click humano y lo deja en el log (así se ve enseguida en Render)."""
    from .models import ClickWhatsAppDetalle
    ip = ip_real(request)
    referer = (request.META.get('HTTP_REFERER') or '')[:500]
    gclid = gclid_del_referer(referer)
    agente = (request.META.get('HTTP_USER_AGENT') or '')[:300]
    ClickWhatsAppDetalle.objects.create(
        psicologo=psicologo, ip=ip[:45], cabeceras=cabeceras_crudas(request), user_agent=agente,
        referer=referer, gclid=gclid,
    )
    registro.info('WA-CLICK ip=%s prof=%s gclid=%s %s ua=%s', ip, psicologo.slug, gclid or '-',
                  cabeceras_crudas(request), agente[:120])
    if random.random() < 0.02:   # limpieza de vez en cuando, sin necesitar una tarea aparte
        purgar_antiguos()
