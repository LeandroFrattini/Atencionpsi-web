import os

from django.core.files import File
from django.db import migrations

RUTA_FOTO = os.path.join(os.path.dirname(__file__), '..', 'seed_media', 'belen_dieguez.jpg')


def cargar_foto(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    curso = Curso.objects.filter(slug='taller-historia-clinica').first()
    if not curso or curso.presentador_foto:
        return
    with open(RUTA_FOTO, 'rb') as archivo:
        curso.presentador_foto.save('belen_dieguez.jpg', File(archivo), save=True)


def quitar_foto(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(presentador_foto='')


class Migration(migrations.Migration):

    dependencies = [
        ('cursos', '0005_curso_presentador_foto'),
        ('cursos', '0004_taller_hc_presentador_bio'),
    ]

    operations = [
        migrations.RunPython(cargar_foto, quitar_foto),
    ]
