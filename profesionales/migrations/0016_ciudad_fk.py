from django.db import migrations, models
import django.db.models.deletion


def poblar_ciudades(apps, schema_editor):
    """Lee los valores existentes de ciudad (texto) y crea objetos Ciudad."""
    Psicologo = apps.get_model('profesionales', 'Psicologo')
    Ciudad = apps.get_model('profesionales', 'Ciudad')

    for psi in Psicologo.objects.exclude(ciudad=''):
        nombre = psi.ciudad.strip()
        if nombre:
            ciudad_obj, _ = Ciudad.objects.get_or_create(nombre=nombre)
            psi.ciudad_obj = ciudad_obj
            psi.save()


class Migration(migrations.Migration):

    dependencies = [
        ('profesionales', '0015_visita_clickwhatsapp'),
    ]

    operations = [
        # 1. Crear tabla Ciudad
        migrations.CreateModel(
            name='Ciudad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True, verbose_name='Ciudad')),
            ],
            options={
                'verbose_name': 'Ciudad',
                'verbose_name_plural': 'Ciudades',
                'ordering': ['nombre'],
            },
        ),
        # 2. Agregar FK ciudad_obj a Psicologo (nullable)
        migrations.AddField(
            model_name='psicologo',
            name='ciudad_obj',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='profesionales.ciudad',
                verbose_name='Ciudad',
            ),
        ),
        # 3. Poblar Ciudad desde los textos existentes
        migrations.RunPython(poblar_ciudades, migrations.RunPython.noop),
    ]
