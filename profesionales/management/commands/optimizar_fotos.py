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

Las fotos que YA venían de un tamaño razonable no se achican (no hace
falta), pero por ese mismo motivo nunca se resubieron a Supabase, así
que se quedaron con el Cache-Control (o la ausencia de uno) que tenían
antes de que existiera esa configuración -- verificado a mano el
2026-09-28: la mitad de las fotos del sitio seguían así, con "no-cache"
en varias, bajándose enteras en cada visita sin ninguna necesidad. Para
esas este comando borra y vuelve a subir el mismo archivo con el mismo
nombre (mismo contenido, no se re-optimiza de nuevo) solo para que
Supabase le ponga el Cache-Control nuevo.

Por defecto SOLO MUESTRA lo que haría (modo prueba) y no toca nada.
Para aplicar los cambios de verdad hay que pasar --apply.

Uso:
    python manage.py optimizar_fotos            # solo muestra el plan y el ahorro estimado
    python manage.py optimizar_fotos --apply     # aplica los cambios
"""
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from profesionales.models import Psicologo, _foto_optimizada


class Command(BaseCommand):
    help = 'Corrige orientación, achica las fotos que superen el tamaño máximo, y refresca el Cache-Control del resto.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Aplica los cambios (por defecto es un dry-run).')

    def handle(self, *args, **options):
        aplicar = options['apply']
        psicologos = Psicologo.objects.exclude(foto='').exclude(foto__isnull=True).order_by('nombre')

        procesados, refrescados, errores = 0, 0, 0
        ahorro_total_kb = 0.0

        for p in psicologos:
            try:
                peso_antes = p.foto.size
                datos_actuales = p.foto.read()
                p.foto.seek(0)
            except Exception:
                self.stdout.write(self.style.WARNING(
                    f'  ERROR leyendo "{p.nombre}": no se pudo abrir su foto actual, se salteó.'
                ))
                errores += 1
                continue

            nueva = _foto_optimizada(p.foto)

            if nueva is not p.foto:
                # Necesitaba achicarse y/o rotarse.
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
            else:
                # Ya está del tamaño correcto -- igual se resube (mismo
                # nombre, mismo contenido) para que quede con el
                # Cache-Control nuevo en vez del que tenía de antes.
                self.stdout.write(f'  "{p.nombre}": ya estaba bien, se refresca el cache.')
                refrescados += 1
                if aplicar:
                    nombre = p.foto.name
                    # Liberar el handle antes de borrar -- en storage local
                    # (Windows) el archivo sigue "en uso" si no se cierra
                    # primero, y falla el delete. En S3/Supabase no hace
                    # falta pero tampoco molesta.
                    p.foto.close()
                    p.foto.storage.delete(nombre)
                    # storage.save() directo (no foto.save()) -- foto.save()
                    # vuelve a pasar el nombre por upload_to y duplica el
                    # prefijo ("psicologos/psicologos/..."), porque el
                    # nombre que ya tenemos acá viene con el prefijo puesto.
                    p.foto.name = p.foto.storage.save(nombre, ContentFile(datos_actuales))
                    p.save(update_fields=['foto'])

        self.stdout.write('')
        self.stdout.write(
            f'Total: {procesados} para achicar/rotar, {refrescados} para refrescar el cache, {errores} con error.'
        )
        if procesados:
            self.stdout.write(f'Ahorro estimado: {ahorro_total_kb / 1024:.1f} MB de las {procesados} fotos achicadas.')

        if not aplicar and (procesados or refrescados):
            self.stdout.write(self.style.WARNING(
                'Esto fue solo una simulación (dry-run). Para aplicar de verdad: python manage.py optimizar_fotos --apply'
            ))
        elif aplicar:
            self.stdout.write(self.style.SUCCESS('Listo, cambios aplicados.'))
