"""Bloqueo de IPs, que se maneja desde el admin (sin tocar el código ni redeployar).

Una IP (o un rango) bloqueada recibe un 403 en TODO el sitio, así que tampoco puede leer las páginas donde están
los números de WhatsApp. Solo queda libre /admin/, para que nadie pueda dejarse afuera por error.

Cómo se decide si un visitante está bloqueado: se miran TODAS las direcciones que el pedido dice traer
(encabezados de los proxys y cada elemento de X-Forwarded-For), no solo la "mejor estimación". Así, agregar una IP
falsa al principio de X-Forwarded-For no sirve para esquivar el bloqueo: la verdadera sigue estando en la lista.
"""
import ipaddress
import logging

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

registro = logging.getLogger('clicks.whatsapp')

CLAVE_CACHE = 'ips_bloqueadas_v1'
SEGUNDOS_CACHE = 30          # como mucho, un bloqueo nuevo tarda esto en aplicarse (al guardar se aplica ya)
EXENTOS = ('/admin/',)
ENCABEZADOS = ('HTTP_CF_CONNECTING_IP', 'HTTP_TRUE_CLIENT_IP', 'HTTP_X_REAL_IP')
PREFIJO_MINIMO = {4: 16, 6: 32}   # un rango más grande que esto podría dejar afuera a medio país

PAGINA = (
    '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>Acceso restringido</title></head><body style="font-family:Arial,sans-serif;max-width:520px;margin:15vh auto;padding:0 20px;color:#333">'
    '<h1 style="font-size:22px">Acceso restringido</h1>'
    '<p>Detectamos actividad inusual desde tu conexión y por seguridad bloqueamos el acceso.</p>'
    '<p>Si creés que es un error, escribinos a atencionpsi.ar@gmail.com contando desde dónde te conectás.</p></body></html>'
)


def _interna(ip):
    return (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_unspecified or ip.is_multicast)


def normalizar(texto):
    """IP o rango en su forma canónica, o ValueError con un mensaje para mostrarle a quien lo cargó."""
    texto = (texto or '').strip()
    try:
        red = ipaddress.ip_network(texto, strict=False)
    except ValueError:
        raise ValueError('No parece una IP válida. Ejemplos: 190.1.2.3, o un rango como 190.1.2.0/24.')
    if _interna(red.network_address):
        raise ValueError('Esa es una dirección interna (de la red de Render o local), no la de un visitante. No se puede bloquear.')
    if red.prefixlen < PREFIJO_MINIMO[red.version]:
        raise ValueError(f'Ese rango es demasiado grande (mínimo /{PREFIJO_MINIMO[red.version]}): dejaría afuera a muchísima gente.')
    return str(red.network_address) if red.num_addresses == 1 else str(red)


def ips_del_visitante(request):
    """Todas las IPs públicas que el pedido dice traer (sin repetir)."""
    meta = request.META
    valores = [meta.get(nombre, '') for nombre in ENCABEZADOS]
    valores += (meta.get('HTTP_X_FORWARDED_FOR') or '').split(',')
    valores.append(meta.get('REMOTE_ADDR', ''))
    encontradas = []
    for valor in valores:
        try:
            ip = ipaddress.ip_address((valor or '').strip())
        except ValueError:
            continue
        if not _interna(ip) and ip not in encontradas:
            encontradas.append(ip)
    return encontradas


def _redes_bloqueadas():
    redes = cache.get(CLAVE_CACHE)
    if redes is None:
        from .models import IPBloqueada
        redes = []
        vigentes = IPBloqueada.objects.filter(activa=True).filter(Q(hasta__isnull=True) | Q(hasta__gt=timezone.now()))
        for texto in vigentes.values_list('ip', flat=True):
            try:
                redes.append(ipaddress.ip_network(texto, strict=False))
            except ValueError:
                continue
        cache.set(CLAVE_CACHE, redes, SEGUNDOS_CACHE)
    return redes


def invalidar():
    cache.delete(CLAVE_CACHE)


def esta_bloqueada(texto_ip):
    try:
        ip = ipaddress.ip_address((texto_ip or '').strip())
    except ValueError:
        return False
    return any(ip in red for red in _redes_bloqueadas())


class BloqueoDeIPsMiddleware:
    """Responde 403 a las IPs bloqueadas. Nunca rompe el sitio: si no puede consultar la lista, deja pasar."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(EXENTOS):
            try:
                redes = _redes_bloqueadas()
                if redes:
                    for ip in ips_del_visitante(request):
                        if any(ip in red for red in redes):
                            registro.info('IP-BLOQUEADA ip=%s %s %s', ip, request.method, request.path[:120])
                            respuesta = HttpResponse(PAGINA, status=403, content_type='text/html; charset=utf-8')
                            respuesta['X-Robots-Tag'] = 'noindex, nofollow'
                            respuesta['Cache-Control'] = 'no-store'
                            return respuesta
            except Exception:
                registro.exception('No se pudo revisar la lista de IPs bloqueadas')
        return self.get_response(request)
