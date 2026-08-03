"""
Corrige tildes y define el orden de aparición de los "Públicos"
(destinatarios: Niños, Adolescentes, Adicciones, etc.).

Por defecto SOLO MUESTRA lo que haría (modo prueba) y no toca la base.
Para aplicar los cambios de verdad hay que pasar --apply.

Uso:
    python manage.py normalizar_publicos            # solo muestra el plan
    python manage.py normalizar_publicos --apply     # aplica los cambios
"""
from django.core.management.base import BaseCommand

from profesionales.models import Publico

PRIORIDAD = {
    'Niños': 0,
    'Adolescentes': 1,
    'Jóvenes': 2,
    'Adultos': 3,
}

# (nombre tal como puede estar cargado hoy, nombre corregido)
PUBLICOS = [
    ('Adicciones', 'Adicciones'),
    ('Neurodivergencias', 'Neurodivergencias'),
    ('Adultos Mayores', 'Adultos Mayores'),
    ('Deportistas', 'Deportistas'),
    ('Abuso Infantil', 'Abuso Infantil'),
    ('Patologías Complejas', 'Patologías Complejas'),
    ('Enfermedades Organicas', 'Enfermedades Orgánicas'),
    ('Perinatal', 'Perinatal'),
    ('Violencia', 'Violencia'),
    ('Maternidades', 'Maternidades'),
    ('Asesoría Laboral', 'Asesoría Laboral'),
    ('Pericias', 'Pericias'),
    ('Jovenes', 'Jóvenes'),
    ('Diversidades', 'Diversidades'),
    ('Orientación a Padres', 'Orientación a Padres'),
    ('Orientación Vocacional', 'Orientación Vocacional'),
    ('Familias', 'Familias'),
    ('Parejas', 'Parejas'),
    ('Niños', 'Niños'),
    ('Adolescentes', 'Adolescentes'),
    ('Adultos', 'Adultos'),
]


class Command(BaseCommand):
    help = 'Corrige tildes y ordena los Públicos. Por defecto es solo un dry-run.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Aplica los cambios de verdad. Sin este flag solo se muestra el plan.',
        )

    def handle(self, *args, **options):
        aplicar = options['apply']

        existentes = list(Publico.objects.all())
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Públicos que ya existen en la base ({len(existentes)}):'
        ))
        for p in existentes:
            self.stdout.write(f'  [id={p.id}] orden={p.orden}  "{p.nombre}"')

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Plan de cambios:'))

        nombres_cubiertos = set()
        for nombre_actual, nombre_correcto in PUBLICOS:
            orden = PRIORIDAD.get(nombre_correcto, 100)
            match = Publico.objects.filter(nombre__in={nombre_actual, nombre_correcto}).first()

            if match:
                nombres_cubiertos.add(match.nombre)
                if match.nombre != nombre_correcto or match.orden != orden:
                    self.stdout.write(
                        f'  ACTUALIZAR id={match.id}: "{match.nombre}" (orden={match.orden}) '
                        f'-> "{nombre_correcto}" (orden={orden})'
                    )
                    if aplicar:
                        match.nombre = nombre_correcto
                        match.orden = orden
                        match.save(update_fields=['nombre', 'orden'])
                else:
                    self.stdout.write(f'  SIN CAMBIOS id={match.id}: "{nombre_correcto}" ya está OK')
            else:
                self.stdout.write(self.style.WARNING(
                    f'  CREAR nuevo: "{nombre_correcto}" (orden={orden}) — no encontré nada parecido en la base'
                ))
                if aplicar:
                    nuevo = Publico.objects.create(nombre=nombre_correcto, orden=orden)
                    nombres_cubiertos.add(nuevo.nombre)

        sin_tocar = [p for p in existentes if p.nombre not in nombres_cubiertos]
        if sin_tocar:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Estos ya existían y NO están en tu lista nueva, no los toco:'
            ))
            for p in sin_tocar:
                self.stdout.write(f'  [id={p.id}] "{p.nombre}"')

        self.stdout.write('')
        if aplicar:
            self.stdout.write(self.style.SUCCESS('Listo, cambios aplicados.'))
        else:
            self.stdout.write(self.style.WARNING(
                'Esto fue solo una simulación (dry-run). No se cambió nada. '
                'Para aplicar de verdad: python manage.py normalizar_publicos --apply'
            ))
