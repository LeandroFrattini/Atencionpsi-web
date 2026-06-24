from django.db import migrations, models


# Obras sociales/prepagas comunes en Argentina
OBRAS_SOCIALES_INICIALES = [
    'PAMI',
    'OSDE',
    'Swiss Medical',
    'Galeno',
    'Medifé',
    'IOMA',
    'Medicus',
    'OMINT',
    'Accord Salud',
    'OSECAC',
    'Sancor Salud',
    'Federada Salud',
    'Particular (sin obra social)',
]


def crear_obras_sociales(apps, schema_editor):
    ObraSocial = apps.get_model('profesionales', 'ObraSocial')
    for nombre in OBRAS_SOCIALES_INICIALES:
        ObraSocial.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):

    dependencies = [
        ('profesionales', '0016_ciudad_fk'),
    ]

    operations = [
        # 1. Crear tabla ObraSocial
        migrations.CreateModel(
            name='ObraSocial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True, verbose_name='Nombre')),
            ],
            options={
                'verbose_name': 'Obra Social / Prepaga',
                'verbose_name_plural': 'Obras Sociales / Prepagas',
                'ordering': ['nombre'],
            },
        ),
        # 2. Reemplazar TextField obras_sociales por M2M
        migrations.RemoveField(
            model_name='psicologo',
            name='obras_sociales',
        ),
        migrations.AddField(
            model_name='psicologo',
            name='obras_sociales',
            field=models.ManyToManyField(
                blank=True,
                to='profesionales.obrasocial',
                verbose_name='Obras Sociales / Prepagas',
            ),
        ),
        # 3. Agregar campo nota_facturacion
        migrations.AddField(
            model_name='psicologo',
            name='nota_facturacion',
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name='Nota de facturación',
                help_text='Ej: Hace facturas para reintegro',
            ),
        ),
        # 4. Poblar lista inicial de OS
        migrations.RunPython(crear_obras_sociales, migrations.RunPython.noop),
    ]
