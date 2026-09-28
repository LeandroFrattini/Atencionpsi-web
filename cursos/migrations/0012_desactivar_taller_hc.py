from django.db import migrations

# El botón de "Formación" de la navbar se sacó del sitio (el checkout de
# Mercado Pago no terminó de andar bien, pedido explícito de desactivarlo
# por ahora). Con esto el curso ya cargado deja de aceptar inscripciones
# aunque alguien tenga el link guardado (Curso.activo=False -> 404 en la
# página del curso, no aparece en el listado de /formacion/). No se borra
# nada -- ni el curso ni las inscripciones ya pagadas -- así se puede
# reactivar con un solo campo el día que se retome.


def desactivar(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(activo=False)


def reactivar(apps, schema_editor):
    Curso = apps.get_model('cursos', 'Curso')
    Curso.objects.filter(slug='taller-historia-clinica').update(activo=True)


class Migration(migrations.Migration):

    dependencies = [
        ('cursos', '0011_cargar_email_presentadora_hc'),
    ]

    operations = [
        migrations.RunPython(desactivar, reactivar),
    ]
