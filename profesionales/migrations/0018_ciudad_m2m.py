from django.db import migrations, models


def fk_a_m2m(apps, schema_editor):
    """Copia el valor de ciudad_obj (FK) al nuevo campo ciudades (M2M)."""
    Psicologo = apps.get_model('profesionales', 'Psicologo')
    for psi in Psicologo.objects.filter(ciudad_obj__isnull=False):
        psi.ciudades.add(psi.ciudad_obj)


class Migration(migrations.Migration):

    dependencies = [
        ('profesionales', '0017_obrasocial'),
    ]

    operations = [
        # 1. Crear la nueva relación M2M
        migrations.AddField(
            model_name='psicologo',
            name='ciudades',
            field=models.ManyToManyField(blank=True, to='profesionales.ciudad', verbose_name='Ciudades'),
        ),
        # 2. Copiar datos del FK al M2M
        migrations.RunPython(fk_a_m2m, migrations.RunPython.noop),
        # 3. Eliminar el FK viejo
        migrations.RemoveField(
            model_name='psicologo',
            name='ciudad_obj',
        ),
    ]
