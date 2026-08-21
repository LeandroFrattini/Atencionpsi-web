import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from portal import mercadopago_client
from portal.models import Pago
from profesionales.models import Psicologo


class Command(BaseCommand):
    help = (
        'Trae los pagos aprobados de la cuenta de Mercado Pago de la dueña de los '
        'últimos N días y crea registros de Pago (sin asignar a ningún profesional '
        'todavía, salvo que el nombre del pagador coincida claramente con uno -- '
        'eso se confirma a mano desde el Panel de Finanzas). Nunca importa dos veces '
        'el mismo pago (se identifica por mp_payment_id). '
        'Dry-run por defecto: usar --apply para guardar de verdad.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Guarda los pagos de verdad (si no, solo muestra el plan)')
        parser.add_argument('--dias', type=int, default=7, help='Cuántos días hacia atrás buscar (default: 7)')

    def handle(self, *args, **options):
        aplicar = options['apply']
        dias = options['dias']
        hasta = timezone.localdate()
        desde = hasta - datetime.timedelta(days=dias)

        try:
            resultados = mercadopago_client.buscar_pagos(desde, hasta)
        except RuntimeError as error:
            self.stderr.write(self.style.ERROR(str(error)))
            return
        except Exception as error:
            self.stderr.write(self.style.ERROR(f'No se pudo consultar Mercado Pago: {error}'))
            return

        ya_importados = set(
            Pago.objects.exclude(mp_payment_id='').exclude(mp_payment_id__isnull=True)
            .values_list('mp_payment_id', flat=True)
        )
        psicologos_activos = list(Psicologo.objects.filter(activo=True))

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Pagos aprobados en Mercado Pago entre {desde} y {hasta}'
        ))

        nuevos = 0
        for crudo in resultados:
            datos = mercadopago_client.normalizar_pago(crudo)
            if not datos or datos['mp_payment_id'] in ya_importados:
                continue

            sugerido = mercadopago_client.sugerir_psicologo(datos['pagador_nombre'], psicologos_activos)
            etiqueta_sugerido = f' -- posible: {sugerido.nombre}' if sugerido else ' -- sin asignar'

            self.stdout.write(
                f"  {datos['fecha']} · {datos['pagador_nombre'] or '(sin nombre)'} · "
                f"{datos['origen']} · neto ${datos['monto']} (bruto ${datos['monto_bruto']})"
                f"{etiqueta_sugerido}"
            )
            nuevos += 1

            if aplicar:
                Pago.objects.create(psicologo=sugerido, **datos)

        if not nuevos:
            self.stdout.write('  (nada nuevo para importar)')

        if aplicar:
            self.stdout.write(self.style.SUCCESS(f'Listo, se importaron {nuevos} pagos nuevos.'))
        else:
            self.stdout.write(self.style.WARNING(
                f'Esto fue solo una simulación (dry-run) -- {nuevos} pagos nuevos sin guardar. '
                'Para guardarlos de verdad: python manage.py sincronizar_pagos_mercadopago --apply'
            ))
