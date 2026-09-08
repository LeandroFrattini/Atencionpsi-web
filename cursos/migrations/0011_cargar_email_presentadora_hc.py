from django.db import migrations

EMAIL_BELEN_DIEGUEZ = 'belendieguez.psi@gmail.com'


def cargar_email(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(
        presentador_email=EMAIL_BELEN_DIEGUEZ,
    )


def quitar_email(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(
        presentador_email='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('cursos', '0010_curso_presentador_email'),
    ]

    operations = [
        migrations.RunPython(cargar_email, quitar_email),
    ]
