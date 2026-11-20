from datetime import timedelta

from django.db import migrations
from django.utils import timezone

# IPs que estuvieron recorriendo a los profesionales uno por uno (2026-11-20). Se cargan solas al desplegar y después
# se manejan desde el admin («IPs bloqueadas»). La de Claro es una red de celulares compartida por muchas personas:
# se bloquea solo 7 días para no dejar afuera a pacientes reales.
IPS = [
    ('142.249.120.173', 'Recorrió a los profesionales uno por uno (Lumen/Level 3 Argentina)', None),
    ('181.239.167.157', 'Recorrió a los profesionales uno por uno (Claro Argentina, red compartida)', timedelta(days=7)),
]


def bloquear(apps, schema_editor):
    IPBloqueada = apps.get_model('profesionales', 'IPBloqueada')
    for ip, motivo, plazo in IPS:
        IPBloqueada.objects.get_or_create(
            ip=ip, defaults={'motivo': motivo, 'hasta': (timezone.now() + plazo) if plazo else None},
        )


def desbloquear(apps, schema_editor):
    apps.get_model('profesionales', 'IPBloqueada').objects.filter(ip__in=[ip for ip, _, _ in IPS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('profesionales', '0030_ip_bloqueada'),
    ]

    operations = [
        migrations.RunPython(bloquear, desbloquear),
    ]
