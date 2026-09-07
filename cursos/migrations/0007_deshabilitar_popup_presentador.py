from django.db import migrations

# La bio queda guardada acá (no se borra el dato, solo se apaga la feature)
# para poder reactivarla mañana con un solo cambio, en vez de reescribirla
# de cero.
BIO_BELEN_DIEGUEZ = (
    'Lic. en Psicología (UBA, 2019). Especialista en Psicología Clínica '
    '(Ministerio de Salud de la Nación, 2025), con residencia hospitalaria '
    'completa en el Hospital Central de San Isidro. Fue Jefa de Residencia '
    '(2024-2025) y hoy es Psicóloga de Guardia en la misma institución. '
    'Cursa la Especialización en Psicología Clínica con Orientación '
    'Psicoanalítica (UBA). Autora y expositora en numerosos congresos '
    'nacionales de salud mental (AASM, APSA).'
)


def apagar_popup(apps, schema_editor):
    # El template solo muestra el nombre como clickeable y arma el modal si
    # presentador_bio no está vacío -- vaciarlo apaga toda la feature sin
    # tocar código (CSS/JS/template siguen ahí, solo quedan sin usarse).
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(presentador_bio='')


def reactivar_popup(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(presentador_bio=BIO_BELEN_DIEGUEZ)


class Migration(migrations.Migration):

    dependencies = [
        ('cursos', '0006_taller_hc_foto'),
    ]

    operations = [
        migrations.RunPython(apagar_popup, reactivar_popup),
    ]
