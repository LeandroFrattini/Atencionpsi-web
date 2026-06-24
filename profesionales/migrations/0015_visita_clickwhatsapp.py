from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('profesionales', '0014_publico_remove_psicologo_dirigido_a_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Visita',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(auto_now_add=True)),
                ('pagina', models.CharField(max_length=200)),
                ('cantidad', models.PositiveIntegerField(default=1)),
            ],
            options={
                'verbose_name': 'Visita',
                'verbose_name_plural': 'Visitas',
                'ordering': ['-fecha'],
                'unique_together': {('fecha', 'pagina')},
            },
        ),
        migrations.CreateModel(
            name='ClickWhatsApp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(auto_now_add=True)),
                ('cantidad', models.PositiveIntegerField(default=1)),
                ('psicologo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clicks_wa', to='profesionales.psicologo')),
            ],
            options={
                'verbose_name': 'Click WhatsApp',
                'verbose_name_plural': 'Clicks WhatsApp',
                'ordering': ['-fecha'],
                'unique_together': {('fecha', 'psicologo')},
            },
        ),
    ]
