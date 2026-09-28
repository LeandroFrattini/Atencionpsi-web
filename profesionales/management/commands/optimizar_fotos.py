"""
Re-procesa las fotos que YA están subidas de los profesionales: corrige
orientación EXIF si hace falta y achica el lado más largo a
FOTO_LADO_MAXIMO si lo excede (ver profesionales/models.py). Las fotos
subidas de acá en adelante ya pasan por esto solas al guardarse -- este
comando es para pasar una sola vez por las que ya estaban cargadas antes
de que existiera el resize automático (fotos de celular sin tocar,
varios MB cada una, sirviéndose así en cada tarjeta del buscador -- la
causa más probable de que Supabase haya cortado el servicio por exceso
de egress el 2026-09-28).

Por defecto SOLO MUESTRA lo que haría (modo prueba) y no toca nada.
Para aplicar los cambios de verdad hay que pasar --apply -- ahí sí
resube cada foto optimizada a Supabase (o al storage local que esté
configurado).

Uso:
    python manage.py optimizar_fotos            # solo muestra el plan y el ahorro estimado
    python manage.py optimizar_fotos --apply     # aplica los cambios
"""
from django.core.management.base import BaseCommand

from profesionales.models import Psicologo, _foto_optimizada


class Command(BaseCommand):
    help = 'Corrige orientación y achica las fotos ya subidas que superen el tamaño máximo.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Aplica los cambios (por defecto es un dry-run).')

    def handle(self, *args, **options):
        aplicar = options['apply']
        psicologos = Psicologo.objects.exclude(foto='').exclude(foto__isnull=True).order_by('nombre')

        procesados, sin_cambios, errores = 0, 0, 0
        ahorro_total_kb = 0.0

        for p in psicologos:
            try:
                peso_antes = p.foto.size
            except Exception:
                self.stdout.write(self.style.WARNING(
                    f'  ERROR leyendo "{p.nombre}": no se pudo abrir su foto actual, se salteó.'
                ))
                errores += 1
                continue

            nueva = _foto_optimizada(p.foto)
            if nueva is p.foto:
                sin_cambios += 1
                continue

            peso_despues = len(nueva.read())
            nueva.seek(0)
            ahorro_kb = (peso_antes - peso_despues) / 1024
            ahorro_total_kb += ahorro_kb
            self.stdout.write(
                f'  "{p.nombre}": {peso_antes / 1024:.0f} KB -> {peso_despues / 1024:.0f} KB '
                f'(-{ahorro_kb:.0f} KB)'
            )
            procesados += 1

            if aplicar:
                p.foto = nueva
                p.save(update_fields=['foto'])

        self.stdout.write('')
        self.stdout.write(
            f'Total: {procesados} para achicar/rotar, {sin_cambios} ya estaban bien, {errores} con error.'
        )
        if procesados:
            self.stdout.write(f'Ahorro estimado: {ahorro_total_kb / 1024:.1f} MB de las {procesados} fotos procesadas.')

        if not aplicar and procesados:
            self.stdout.write(self.style.WARNING(
                'Esto fue solo una simulación (dry-run). Para aplicar de verdad: python manage.py optimizar_fotos --apply'
            ))
        elif aplicar:
            self.stdout.write(self.style.SUCCESS('Listo, cambios aplicados.'))
