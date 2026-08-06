"""
Pasa a minúscula el username/email de los usuarios del portal (el
username siempre es el email cargado). Si quedó guardado con mayúsculas
mezcladas (p.ej. "Juan.Perez@Gmail.com") y el profesional lo escribe
distinto al loguearse, el login falla aunque la contraseña esté bien
-- esto corrige a los que ya están cargados así.

Solo toca usuarios que están ligados a un Psicologo (no la cuenta de la
dueña del sitio ni ningún otro usuario del admin).

Por defecto SOLO MUESTRA lo que haría (modo prueba) y no toca la base.
Para aplicar los cambios de verdad hay que pasar --apply.

Uso:
    python manage.py normalizar_emails_usuario            # solo muestra el plan
    python manage.py normalizar_emails_usuario --apply     # aplica los cambios
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from profesionales.models import Psicologo


class Command(BaseCommand):
    help = 'Pasa a minúscula el username/email de los usuarios del portal. Por defecto es solo un dry-run.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Aplica los cambios de verdad. Sin este flag solo se muestra el plan.',
        )

    def handle(self, *args, **options):
        aplicar = options['apply']

        usuarios = User.objects.filter(psicologo__isnull=False).select_related('psicologo')

        cambiados, sin_cambios, en_conflicto = 0, 0, 0
        for user in usuarios:
            nuevo_username = user.username.strip().lower()
            nuevo_email = user.email.strip().lower()

            if nuevo_username == user.username and nuevo_email == user.email:
                sin_cambios += 1
                continue

            ya_existe_otro = User.objects.filter(username=nuevo_username).exclude(pk=user.pk).exists()
            if ya_existe_otro:
                self.stdout.write(self.style.WARNING(
                    f'  CONFLICTO "{user.psicologo.nombre}": ya hay otra cuenta con username "{nuevo_username}" -- revisar a mano'
                ))
                en_conflicto += 1
                continue

            self.stdout.write(
                f'  "{user.psicologo.nombre}": "{user.username}" -> "{nuevo_username}"'
            )
            cambiados += 1
            if aplicar:
                user.username = nuevo_username
                user.email = nuevo_email
                user.save(update_fields=['username', 'email'])

        self.stdout.write('')
        self.stdout.write(
            f'Total: {cambiados} para corregir, {sin_cambios} ya estaban bien, {en_conflicto} en conflicto (revisar a mano).'
        )
        self.stdout.write('')
        if aplicar:
            self.stdout.write(self.style.SUCCESS('Listo, cambios aplicados.'))
        else:
            self.stdout.write(self.style.WARNING(
                'Esto fue solo una simulación (dry-run). No se cambió nada. '
                'Para aplicar de verdad: python manage.py normalizar_emails_usuario --apply'
            ))
