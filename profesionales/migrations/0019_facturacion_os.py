from django.db import migrations


NUEVAS_OPCIONES = [
    'Hace factura para reintegro',
    'No realiza factura',
]


def agregar_opciones(apps, schema_editor):
    ObraSocial = apps.get_model('profesionales', 'ObraSocial')
    for nombre in NUEVAS_OPCIONES:
        ObraSocial.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ('profesionales', '0018_ciudad_m2m'),
    ]

    operations = [
        migrations.RunPython(agregar_opciones, migrations.RunPython.noop),
    ]
