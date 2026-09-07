"""
Creación de checkouts de Mercado Pago (Checkout Pro) para inscripciones a
cursos. Usa el mismo MERCADOPAGO_ACCESS_TOKEN que portal/mercadopago_client.py
(misma cuenta, distinto uso: acá se crea un cobro nuevo en vez de solo leer
el historial).
"""
import os

import requests
from django.urls import reverse

API_BASE = 'https://api.mercadopago.com'


def _token():
    return os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')


def crear_preferencia(inscripcion, request):
    """Crea la preferencia de pago en Mercado Pago para esta inscripción y
    devuelve el JSON de la API (trae 'id' y 'init_point', la URL del
    checkout hosteado). external_reference queda con el pk de la
    inscripción para poder identificarla de vuelta en el webhook."""
    token = _token()
    if not token:
        raise RuntimeError(
            'Falta la variable de entorno MERCADOPAGO_ACCESS_TOKEN -- sin eso '
            'no se puede crear un cobro en Mercado Pago.'
        )

    base_url = f'{request.scheme}://{request.get_host()}'
    # Armadas con reverse() (no a mano) para que nunca queden desincronizadas
    # del mount real de cursos.urls en atencionpsi/urls.py -- antes decían
    # "/cursos/..." hardcodeado, pero la app está montada en "/formacion/",
    # así que tanto la vuelta del pago como el webhook de Mercado Pago
    # apuntaban a un 404 real y jamás confirmaban nada.
    url_resultado = base_url + reverse('cursos_resultado', args=[inscripcion.pk])
    url_webhook = base_url + reverse('cursos_webhook_mercadopago')
    body = {
        'items': [{
            'title': inscripcion.curso.nombre,
            'quantity': 1,
            'unit_price': float(inscripcion.monto),
            'currency_id': 'ARS',
        }],
        'payer': {'name': inscripcion.nombre, 'email': inscripcion.email},
        'external_reference': str(inscripcion.pk),
        'back_urls': {
            'success': url_resultado,
            'pending': url_resultado,
            'failure': url_resultado,
        },
        'auto_return': 'approved',
        'notification_url': url_webhook,
    }
    resp = requests.post(
        f'{API_BASE}/checkout/preferences', json=body,
        headers={'Authorization': f'Bearer {token}'}, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def obtener_pago(mp_payment_id):
    """Trae el detalle de un pago por id -- lo usa el webhook para
    confirmar el estado real en vez de confiar ciegamente en lo que venga
    en la notificación (Mercado Pago recomienda esto explícitamente)."""
    token = _token()
    resp = requests.get(
        f'{API_BASE}/v1/payments/{mp_payment_id}',
        headers={'Authorization': f'Bearer {token}'}, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
