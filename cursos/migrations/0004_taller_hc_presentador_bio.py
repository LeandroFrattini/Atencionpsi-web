from django.db import migrations


BIO_BELEN_DIEGUEZ = (
    'Lic. en Psicología (UBA, 2019). Especialista en Psicología Clínica '
    '(Ministerio de Salud de la Nación, 2025), con residencia hospitalaria '
    'completa en el Hospital Central de San Isidro. Fue Jefa de Residencia '
    '(2024-2025) y hoy es Psicóloga de Guardia en la misma institución. '
    'Cursa la Especialización en Psicología Clínica con Orientación '
    'Psicoanalítica (UBA). Autora y expositora en numerosos congresos '
    'nacionales de salud mental (AASM, APSA).'
)


def completar_bio(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(presentador_bio=BIO_BELEN_DIEGUEZ)


def vaciar_bio(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(presentador_bio='')


class Migration(migrations.Migration):

    dependencies = [
        ('cursos', '0003_curso_presentador_bio'),
        ('cursos', '0002_taller_historia_clinica'),
    ]

    operations = [
        migrations.RunPython(completar_bio, vaciar_bio),
    ]
