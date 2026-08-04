"""
Lee el texto libre que cada profesional escribió en Psicologo.orientacion
y le marca las categorías fijas de Orientacion que le correspondan, para
que el filtro del buscador funcione. NO toca ni borra el texto libre --
solo agrega las etiquetas.

Por defecto SOLO MUESTRA lo que haría (modo prueba) y no toca la base.
Para aplicar los cambios de verdad hay que pasar --apply.

El mapeo es por palabras clave, así que un texto como "Terapia cognitivo
conductual y sistémica" le marca DOS categorías (Cognitivo Conductual y
Sistémica) a la vez -- es normal y esperado, muchos profesionales
combinan enfoques.

Los que no matchean ninguna palabra clave quedan listados aparte al
final ("SIN MAPEAR") para revisar a mano -- no se les asigna "Otras"
en automático, para no perder de vista casos raros o mal escritos.

Uso:
    python manage.py asignar_orientaciones            # solo muestra el plan
    python manage.py asignar_orientaciones --apply     # aplica los cambios
"""
from django.core.management.base import BaseCommand

from profesionales.models import Orientacion, Psicologo

# (nombre de la categoría, orden de aparición en el filtro, palabras clave
# que la disparan -- todo en minúscula y sin tildes, se compara así)
CATEGORIAS = [
    ('Psicoanálisis', 0, ['psicoanal', 'psicodinam', 'piscoanal', 'psiconal']),
    ('Cognitivo Conductual (TCC)', 1, ['cognitiv', 'conductual', 'tcc']),
    ('Sistémica', 2, ['sistem']),
    ('Tercera Ola', 3, ['tercera ola', 'dbt', 'mindfulness', 'contextual', 'aceptacion y compromiso', ' act ', ' act,', ' act-', ' act.']),
    ('Integrativa', 4, ['integrativ', 'integral', 'eclectic']),
    ('Humanista / Existencial', 5, ['humanist', 'existencial']),
    ('Perinatal', 6, ['perinatal']),
]


def _sin_tildes(texto):
    reemplazos = str.maketrans('áéíóúñ', 'aeioun')
    return texto.translate(reemplazos)


def categorias_para_texto(texto_libre):
    """Devuelve la lista de nombres de categoría que matchean ese texto libre."""
    normalizado = ' ' + _sin_tildes(texto_libre.lower()) + ' '
    encontradas = []
    for nombre, _orden, palabras_clave in CATEGORIAS:
        if any(clave in normalizado for clave in palabras_clave):
            encontradas.append(nombre)
    return encontradas


class Command(BaseCommand):
    help = 'Asigna las categorías fijas de Orientacion según el texto libre cargado. Por defecto es solo un dry-run.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Aplica los cambios de verdad. Sin este flag solo se muestra el plan.',
        )

    def handle(self, *args, **options):
        aplicar = options['apply']

        # Asegurar que existan las categorías (igual que normalizar_publicos con Publico)
        categorias_db = {}
        for nombre, orden, _claves in CATEGORIAS:
            existente = Orientacion.objects.filter(nombre=nombre).first()
            if existente:
                if existente.orden != orden:
                    self.stdout.write(f'  ACTUALIZAR orden de "{nombre}": {existente.orden} -> {orden}')
                    if aplicar:
                        existente.orden = orden
                        existente.save(update_fields=['orden'])
                categorias_db[nombre] = existente
            else:
                self.stdout.write(self.style.WARNING(f'  CREAR categoría nueva: "{nombre}" (orden={orden})'))
                if aplicar:
                    categorias_db[nombre] = Orientacion.objects.create(nombre=nombre, orden=orden)

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Plan de asignación por profesional:'))

        sin_mapear = []
        for psico in Psicologo.objects.exclude(orientacion='').order_by('nombre'):
            categorias_encontradas = categorias_para_texto(psico.orientacion)

            if not categorias_encontradas:
                sin_mapear.append(psico)
                continue

            ya_tiene = set(psico.orientaciones.values_list('nombre', flat=True))
            nuevas = [c for c in categorias_encontradas if c not in ya_tiene]

            if not nuevas:
                self.stdout.write(f'  SIN CAMBIOS "{psico.nombre}": ya tiene {sorted(ya_tiene)}')
                continue

            self.stdout.write(
                f'  "{psico.nombre}" (orientacion="{psico.orientacion}") -> {categorias_encontradas}'
            )
            if aplicar:
                for nombre_cat in nuevas:
                    cat = categorias_db.get(nombre_cat) or Orientacion.objects.get(nombre=nombre_cat)
                    psico.orientaciones.add(cat)

        if sin_mapear:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'SIN MAPEAR ({len(sin_mapear)}) -- ninguna palabra clave matcheó, revisar a mano:'
            ))
            for psico in sin_mapear:
                self.stdout.write(f'  [id={psico.id}] "{psico.nombre}": orientacion="{psico.orientacion}"')

        self.stdout.write('')
        if aplicar:
            self.stdout.write(self.style.SUCCESS('Listo, cambios aplicados.'))
        else:
            self.stdout.write(self.style.WARNING(
                'Esto fue solo una simulación (dry-run). No se cambió nada. '
                'Para aplicar de verdad: python manage.py asignar_orientaciones --apply'
            ))
