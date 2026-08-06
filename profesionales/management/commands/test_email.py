"""
Manda un mail de prueba (con datos ficticios) para validar que la
configuración de Brevo (BREVO_SMTP_LOGIN / BREVO_SMTP_KEY) funciona de
punta a punta, sin depender de que exista un Turno real todavía.

Uso:
    python manage.py test_email
    python manage.py test_email --to otra@direccion.com
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from portal.notificaciones import contexto_de_ejemplo, enviar_con_contexto


class Command(BaseCommand):
    help = 'Manda un mail de prueba para validar la configuración de envío (Brevo).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to', dest='destino', default=None,
            help='Email de destino. Por defecto usa TURNOS_BCC_EMAIL de settings.',
        )

    def handle(self, *args, **options):
        destino = options['destino'] or settings.TURNOS_BCC_EMAIL
        if not destino:
            self.stderr.write(self.style.ERROR(
                'No hay destino: pasá --to tu@mail.com o configurá TURNOS_BCC_EMAIL.'
            ))
            return

        self.stdout.write(f'Mandando mail de prueba a {destino}...')
        enviar_con_contexto(destino, contexto_de_ejemplo())
        self.stdout.write(self.style.SUCCESS(f'Listo, revisá la bandeja de {destino}.'))
