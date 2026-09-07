import datetime

from django.db import migrations


DESCRIPCION = (
    'Taller práctico y en vivo: breve repaso del marco legal de la historia clínica '
    'y ejemplos reales de registro.\n\n'
    'La dinámica es compartir pantalla de Word e ir escribiendo en vivo cómo dejarían '
    'registro de las situaciones clínicas que les generen dudas -- puliendo ese registro '
    'entre todo el grupo, con los aportes de cada uno.\n\n'
    'Duración: 2:30 horas.'
)


def crear_curso(apps, schema_editor):
    # get_or_create por slug: si alguien ya lo cargó a mano desde el admin
    # antes de que corra esta migración, no lo duplica ni lo pisa.
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.get_or_create(
        slug='taller-historia-clinica',
        defaults=dict(
            nombre='Taller de Escritura de Historia Clínica',
            presentador='Lic. Belén Dieguez',
            presentador_detalle='Esp. en Psicología Clínica · UBA',
            fecha=datetime.date(2026, 9, 26),
            hora=datetime.time(10, 0),
            descripcion=DESCRIPCION,
            precio_red_consulta=17500,
            precio_publico=27500,
            activo=True,
        ),
    )


def eliminar_curso(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('cursos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_curso, eliminar_curso),
    ]
