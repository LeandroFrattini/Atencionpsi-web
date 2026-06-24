from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('profesionales', '0019_facturacion_os'),
    ]

    operations = [
        migrations.AddField(
            model_name='ciudad',
            name='ciudad_padre',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='barrios',
                to='profesionales.ciudad',
                verbose_name='Ciudad padre',
            ),
        ),
        migrations.AlterField(
            model_name='ciudad',
            name='nombre',
            field=models.CharField(max_length=100, verbose_name='Nombre'),
        ),
        migrations.AlterUniqueTogether(
            name='ciudad',
            unique_together={('nombre', 'ciudad_padre')},
        ),
        migrations.AlterModelOptions(
            name='ciudad',
            options={
                'ordering': ['ciudad_padre__nombre', 'nombre'],
                'verbose_name': 'Ciudad',
                'verbose_name_plural': 'Ciudades',
            },
        ),
    ]
