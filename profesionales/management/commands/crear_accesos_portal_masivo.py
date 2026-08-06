"""
Alta masiva de accesos al portal (/portal/) para varios profesionales
a la vez, a partir de una lista de (nombre, email, teléfono) en CSV.

El teléfono se usa como contraseña inicial (igual que en el alta
individual desde el admin) y queda marcado el cambio obligatorio en
el primer ingreso.

El match contra Psicologo es por nombre (normalizado, sin tildes,
sin importar mayúsculas/orden de palabras). Si no encuentra un match
único, o el profesional ya tiene un usuario asignado, NO TOCA nada
y lo deja listado para revisar a mano.

Por defecto SOLO MUESTRA lo que haría (modo prueba) y no toca la base.
Para aplicar los cambios de verdad hay que pasar --apply.

IMPORTANTE: el CSV con los datos reales (nombres, emails, teléfonos)
NUNCA se guarda en el repo -- es información personal de los
profesionales. Se pasa por stdin o con --csv apuntando a un archivo
local que quede fuera de git.

Formato del CSV (sin encabezado): nombre,email,telefono

Uso:
    python manage.py crear_accesos_portal_masivo < datos.csv
    python manage.py crear_accesos_portal_masivo --csv datos.csv
    python manage.py crear_accesos_portal_masivo --csv datos.csv --apply
"""
import csv
import re
import sys

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from profesionales.models import Psicologo


def _normalizar(texto):
    texto = texto.translate(str.maketrans('áéíóúÁÉÍÓÚñÑ', 'aeiouAEIOUnN'))
    return texto.strip().lower()


def _buscar_psicologo(nombre_mensaje):
    """Busca un match único por nombre, tolerando tildes/orden de palabras."""
    objetivo = set(_normalizar(nombre_mensaje).split())
    candidatos = []
    for psico in Psicologo.objects.all():
        tokens_psico = set(_normalizar(psico.nombre).split())
        if objetivo <= tokens_psico or tokens_psico <= objetivo:
            candidatos.append(psico)
    return candidatos


class Command(BaseCommand):
    help = 'Crea accesos al portal para varios profesionales a la vez, desde un CSV. Por defecto es solo un dry-run.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv', dest='csv_path', default=None,
            help='Ruta a un CSV local (nombre,email,telefono) que NO esté en el repo. '
                 'Si no se pasa, lee el CSV de stdin.',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='Aplica los cambios de verdad. Sin este flag solo se muestra el plan.',
        )

    def handle(self, *args, **options):
        aplicar = options['apply']

        if options['csv_path']:
            f = open(options['csv_path'], newline='', encoding='utf-8')
        else:
            if sys.stdin.isatty():
                raise CommandError(
                    'No pasaste --csv y no hay nada en stdin. '
                    'Usá: manage.py crear_accesos_portal_masivo --csv archivo.csv '
                    'o pegá el CSV por stdin.'
                )
            f = sys.stdin

        try:
            filas = [fila for fila in csv.reader(f) if fila and fila[0].strip()]
        finally:
            if f is not sys.stdin:
                f.close()

        if not filas:
            raise CommandError('El CSV está vacío.')

        self.stdout.write(self.style.MIGRATE_HEADING(f'Plan de altas ({len(filas)} en la lista):'))

        creados, saltados = 0, 0
        for fila in filas:
            if len(fila) < 3:
                self.stdout.write(self.style.WARNING(f'  FILA INVÁLIDA (faltan columnas): {fila}'))
                saltados += 1
                continue
            nombre, email, telefono = (x.strip() for x in fila[:3])
            candidatos = _buscar_psicologo(nombre)
            password = re.sub(r'[^\d]', '', telefono)

            if len(candidatos) == 0:
                self.stdout.write(self.style.WARNING(f'  NO ENCONTRADO en la base: "{nombre}" — revisar a mano'))
                saltados += 1
                continue
            if len(candidatos) > 1:
                nombres_match = ', '.join(f'"{c.nombre}" (id={c.id})' for c in candidatos)
                self.stdout.write(self.style.WARNING(f'  AMBIGUO "{nombre}": matchea con varios -> {nombres_match}'))
                saltados += 1
                continue

            psico = candidatos[0]

            if psico.usuario_id:
                self.stdout.write(
                    f'  YA TIENE ACCESO "{psico.nombre}" (usuario actual: {psico.usuario.username}) — no lo toco'
                )
                saltados += 1
                continue

            conflicto = User.objects.filter(username__iexact=email).exists()
            if conflicto:
                self.stdout.write(self.style.WARNING(
                    f'  CONFLICTO "{psico.nombre}": ya existe un usuario con el email {email} — revisar a mano'
                ))
                saltados += 1
                continue

            self.stdout.write(f'  CREAR "{psico.nombre}" (id={psico.id}): usuario={email}')
            creados += 1
            if aplicar:
                user = User(username=email, email=email)
                user.is_staff = False
                user.is_superuser = False
                user.set_password(password)
                user.save()
                psico.usuario = user
                psico.debe_cambiar_password = True
                psico.save(update_fields=['usuario', 'debe_cambiar_password'])

        self.stdout.write('')
        self.stdout.write(f'Total: {creados} para crear, {saltados} saltados/a revisar.')
        self.stdout.write('')
        if aplicar:
            self.stdout.write(self.style.SUCCESS('Listo, cambios aplicados.'))
        else:
            self.stdout.write(self.style.WARNING(
                'Esto fue solo una simulación (dry-run). No se cambió nada. '
                'Para aplicar de verdad, agregá --apply.'
            ))
