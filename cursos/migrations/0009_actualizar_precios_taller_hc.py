from django.db import migrations

# Precios anteriores, guardados acá para poder revertir sin adivinar.
PRECIO_MIEMBROS_ANTES = 17500
PRECIO_PUBLICO_ANTES = 27500

PRECIO_MIEMBROS_AHORA = 15000
PRECIO_PUBLICO_AHORA = 25000


def actualizar_precios(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(
        precio_red_consulta=PRECIO_MIEMBROS_AHORA,
        precio_publico=PRECIO_PUBLICO_AHORA,
    )


def revertir_precios(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(
        precio_red_consulta=PRECIO_MIEMBROS_ANTES,
        precio_publico=PRECIO_PUBLICO_ANTES,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('cursos', '0008_alter_curso_precio_red_consulta'),
    ]

    operations = [
        migrations.RunPython(actualizar_precios, revertir_precios),
    ]
