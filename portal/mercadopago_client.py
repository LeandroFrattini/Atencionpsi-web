"""
Lectura de pagos desde la cuenta de Mercado Pago de la dueña del sitio.
Solo lectura -- nunca crea ni modifica cobros, solo trae el historial para
completar solo los registros de Pago que hoy se cargan a mano.

Requiere la variable de entorno MERCADOPAGO_ACCESS_TOKEN (token de
producción, "APP_USR-..."). En Render se carga como variable de entorno,
nunca como texto en el repo.
"""
import datetime
import os
from decimal import Decimal

import requests
from django.utils import timezone

API_BASE = 'https://api.mercadopago.com'


def _token():
    return os.environ.get('MERCADOPAGO_ACCESS_TOKEN', '')


def mi_user_id():
    """
    ID de cuenta de MP de la dueña. Se usa para distinguir plata que le
    entra de plata que ella misma mueve (una transferencia que manda, o
    una carga a su propia cuenta) -- ver normalizar_pago(). Devuelve None
    si no se pudo consultar (sin token, o falla de red); en ese caso
    normalizar_pago() sigue funcionando, solo que sin ese chequeo extra.
    """
    token = _token()
    if not token:
        return None
    try:
        resp = requests.get(
            f'{API_BASE}/users/me',
            headers={'Authorization': f'Bearer {token}'},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get('id')
    except requests.RequestException:
        return None


def _a_decimal(valor):
    """
    La API manda los montos como float (ej: 31154.659999999998). Convertir
    directo a Decimal arrastra ese error de punto flotante -- pasando por
    str() primero (después de redondear a 2 decimales, como cualquier
    monto de dinero) se guarda limpio.
    """
    return Decimal(str(round(valor, 2)))


def buscar_pagos(desde, hasta, limit=50, offset=0):
    """
    Pagos con date_created en [desde, hasta] (objetos date), más recientes
    primero. Devuelve la lista de resultados tal cual los manda la API --
    ver normalizar_pago() para la conversión a los campos que usamos.
    """
    token = _token()
    if not token:
        raise RuntimeError(
            'Falta la variable de entorno MERCADOPAGO_ACCESS_TOKEN -- '
            'sin eso no se puede consultar la cuenta de Mercado Pago.'
        )

    params = {
        'sort': 'date_created',
        'criteria': 'desc',
        'range': 'date_created',
        'begin_date': f'{desde.isoformat()}T00:00:00.000-03:00',
        'end_date': f'{hasta.isoformat()}T23:59:59.999-03:00',
        'limit': limit,
        'offset': offset,
    }
    resp = requests.get(
        f'{API_BASE}/v1/payments/search',
        headers={'Authorization': f'Bearer {token}'},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get('results', [])


def normalizar_pago(pago_mp, mi_id=None):
    """
    Convierte un resultado crudo de la API a los campos de portal.models.Pago.
    Devuelve None si no corresponde importarlo: no aprobado, o es plata que
    la dueña movió ella misma (una transferencia que mandó afuera, o una
    carga a su propia cuenta) en vez de un cobro real.

    Confirmado con datos reales de la cuenta: un cobro de verdad siempre
    tiene quién lo pagó (payer.id) y esa persona no es la dueña. Una
    transferencia que ella manda no trae payer.id, y una carga a su propia
    cuenta trae payer.id == su propio id -- ninguno de los dos es un
    ingreso, así que ambos se descartan acá.
    """
    if pago_mp.get('status') != 'approved':
        return None

    payer_id = (pago_mp.get('payer') or {}).get('id')
    # La API a veces manda el id como texto ("529282922") y otras como
    # número (529282922) según el tipo de movimiento -- comparar tal cual
    # sin pasar por str() hace que la comparación falle en silencio y deje
    # pasar plata que la dueña se transfirió a sí misma.
    if not payer_id or (mi_id and str(payer_id) == str(mi_id)):
        return None

    monto_bruto = pago_mp.get('transaction_amount') or 0
    if monto_bruto <= 0:
        return None
    monto_bruto = _a_decimal(monto_bruto)

    detalles = pago_mp.get('transaction_details') or {}
    monto_neto = detalles.get('net_received_amount')
    if not monto_neto:
        # Las transferencias entre cuentas de MP no tienen comisión --
        # si la API no manda net_received_amount, el neto es el bruto.
        monto_neto = monto_bruto
    else:
        monto_neto = _a_decimal(monto_neto)

    # El criterio real (confirmado con la dueña) no es preapproval_id --
    # varios pagos por suscripción no lo traen. Lo que realmente distingue
    # una transferencia de una suscripción/cobro con tarjeta es si MP le
    # sacó comisión o no: si el neto es menor al bruto, hubo descuento.
    origen = 'suscripcion' if monto_neto < monto_bruto else 'transferencia'

    payer = pago_mp.get('payer') or {}
    nombre = ' '.join(filter(None, [payer.get('first_name'), payer.get('last_name')])).strip()
    if not nombre:
        nombre = payer.get('email', '')

    fecha_str = pago_mp.get('date_approved') or pago_mp.get('date_created')
    try:
        fecha = datetime.date.fromisoformat(fecha_str[:10]) if fecha_str else timezone.localdate()
    except ValueError:
        fecha = timezone.localdate()

    return {
        'mp_payment_id': str(pago_mp['id']),
        'fecha': fecha,
        'monto': monto_neto,
        'monto_bruto': monto_bruto,
        'origen': origen,
        'pagador_nombre': nombre,
        'concepto': pago_mp.get('description', '') or ('Suscripción' if origen == 'suscripcion' else 'Transferencia'),
    }


def dias_desde_ultimo_pago(default=30, tope=90):
    """
    Cuántos días para atrás hay que mirar para no dejar huecos: desde la
    fecha del último pago que ya se importó de MP, con un día de margen.
    Si nunca se importó ninguno, usa `default`. Nunca más de `tope` para
    no traer sin querer un historial gigante la primera vez que se usa
    después de mucho tiempo sin correrlo.
    """
    from portal.models import Pago

    ultimo = (
        Pago.objects.exclude(mp_payment_id='').exclude(mp_payment_id__isnull=True)
        .order_by('-fecha').first()
    )
    if not ultimo:
        return default
    dias = (timezone.localdate() - ultimo.fecha).days + 1
    return max(1, min(dias, tope))


def importar_pagos_nuevos(dias):
    """
    Trae los pagos aprobados de los últimos `dias` días y crea los Pago que
    falten -- nunca duplica (se identifican por mp_payment_id). A diferencia
    del comando de management, esto siempre guarda (no tiene dry-run): lo
    usa el botón "Actualizar" del Panel de Finanzas, pensado para un click
    directo. Devuelve la lista de Pago recién creados.
    """
    from portal.models import Pago
    from profesionales.models import Psicologo

    hasta = timezone.localdate()
    desde = hasta - datetime.timedelta(days=dias)
    resultados = buscar_pagos(desde, hasta)

    ya_importados = set(
        Pago.objects.exclude(mp_payment_id='').exclude(mp_payment_id__isnull=True)
        .values_list('mp_payment_id', flat=True)
    )
    psicologos_activos = list(Psicologo.objects.filter(activo=True))
    mi_id = mi_user_id()

    creados = []
    for crudo in resultados:
        datos = normalizar_pago(crudo, mi_id=mi_id)
        if not datos or datos['mp_payment_id'] in ya_importados:
            continue
        sugerido = sugerir_psicologo(datos['pagador_nombre'], psicologos_activos)
        creados.append(Pago.objects.create(psicologo=sugerido, **datos))
        ya_importados.add(datos['mp_payment_id'])
    return creados


def sugerir_psicologo(pagador_nombre, psicologos_activos):
    """
    Intento simple de adivinar a qué profesional corresponde un pago, por
    coincidencia de nombre. Nunca se usa para asignar solo -- siempre es
    una sugerencia que la dueña confirma a mano.
    """
    if not pagador_nombre:
        return None
    nombre_normalizado = pagador_nombre.strip().lower()
    for psicologo in psicologos_activos:
        if psicologo.nombre.strip().lower() in nombre_normalizado or nombre_normalizado in psicologo.nombre.strip().lower():
            return psicologo
    return None
