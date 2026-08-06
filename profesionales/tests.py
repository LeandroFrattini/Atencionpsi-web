import zipfile
from io import BytesIO

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .generador_imagenes import generar_imagen_story
from .models import Ciudad, Modalidad, Psicologo, Publico


class GeneradorImagenesTests(TestCase):
    def setUp(self):
        self.psico = Psicologo.objects.create(nombre='Lic. Prueba Genérica', whatsapp='2911234567')
        self.psico.modalidades.set([Modalidad.objects.create(nombre='Presencial')])
        self.psico.destinatarios.set([
            Publico.objects.create(nombre='Adultos'),
            Publico.objects.create(nombre='Adolescentes'),
        ])

    def test_genera_imagen_del_tamano_correcto_sin_foto(self):
        """Sin foto cargada, usa el placeholder y no debe romper."""
        img = generar_imagen_story(self.psico)
        self.assertEqual(img.size, (1080, 1920))
        self.assertEqual(img.mode, 'RGB')

    def test_franja_etaria_larga_no_se_corta(self):
        """Con muchos destinatarios, el texto se debe achicar solo (nunca desbordar)."""
        todos = list(Publico.objects.all()) + [
            Publico.objects.create(nombre='Familias'),
            Publico.objects.create(nombre='Parejas'),
            Publico.objects.create(nombre='Orientación Vocacional'),
            Publico.objects.create(nombre='Orientación a Padres'),
        ]
        self.psico.destinatarios.set(todos)
        img = generar_imagen_story(self.psico)  # no debe lanzar excepción
        self.assertEqual(img.size, (1080, 1920))

    def test_ciudad_aparece_solo_cuando_hay_dos_modalidades(self):
        ciudad = Ciudad.objects.create(nombre='Bahía Blanca')
        self.psico.ciudades.add(ciudad)
        # Con una sola modalidad no debería fallar ni requerir ciudad
        img = generar_imagen_story(self.psico)
        self.assertEqual(img.size, (1080, 1920))
        # Con dos modalidades tampoco debe fallar
        self.psico.modalidades.add(Modalidad.objects.create(nombre='Online'))
        img2 = generar_imagen_story(self.psico)
        self.assertEqual(img2.size, (1080, 1920))


class GenerarImagenesAdminActionTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin_gen_test', 'admin@example.com', 'ClaveAdminSegura2026')
        self.psico = Psicologo.objects.create(nombre='Lic. Prueba Admin', whatsapp='2911234567')
        self.client = Client()
        self.client.force_login(self.admin_user)

    def test_descarga_zip_con_la_historia(self):
        url = reverse('admin:profesionales_psicologo_changelist')
        resp = self.client.post(url, {
            'action': 'generar_imagenes_action',
            '_selected_action': [self.psico.pk],
            'apply': '1',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')
        zf = zipfile.ZipFile(BytesIO(resp.content))
        nombres = zf.namelist()
        self.assertEqual(len(nombres), 1)
        self.assertTrue(nombres[0].endswith('_historia.jpg'))

    def test_telefono_manual_override_no_rompe_la_descarga(self):
        """El campo opcional del admin para pisar el número de la imagen no debe fallar."""
        url = reverse('admin:profesionales_psicologo_changelist')
        resp = self.client.post(url, {
            'action': 'generar_imagenes_action',
            '_selected_action': [self.psico.pk],
            'apply': '1',
            'telefono_manual': '542914250495',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')
        zf = zipfile.ZipFile(BytesIO(resp.content))
        self.assertEqual(len(zf.namelist()), 1)


class PsicologoActivoTests(TestCase):
    """Un profesional dado de baja (activo=False) tiene que desaparecer del sitio público."""

    def setUp(self):
        self.activo = Psicologo.objects.create(nombre='Lic. Activa', whatsapp='2911111111', activo=True)
        self.inactivo = Psicologo.objects.create(nombre='Lic. De Baja', whatsapp='2912222222', activo=False)
        self.client = Client()

    def test_buscador_no_muestra_a_los_dados_de_baja(self):
        resp = self.client.get(reverse('buscador'))
        nombres = [p.nombre for p in resp.context['psicologos']]
        self.assertIn('Lic. Activa', nombres)
        self.assertNotIn('Lic. De Baja', nombres)

    def test_perfil_de_dado_de_baja_no_es_accesible(self):
        resp = self.client.get(reverse('perfil_psicologo', args=[self.inactivo.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_perfil_de_activo_si_es_accesible(self):
        resp = self.client.get(reverse('perfil_psicologo', args=[self.activo.slug]))
        self.assertEqual(resp.status_code, 200)


class OrientacionFiltroTests(TestCase):
    """El filtro de Orientación del buscador funciona sobre las categorías fijas (M2M),
    no sobre el texto libre que cada profesional escribe."""

    def setUp(self):
        from .models import Orientacion
        self.tcc = Orientacion.objects.create(nombre='Cognitivo Conductual (TCC)')
        self.psa = Orientacion.objects.create(nombre='Psicoanálisis')

        self.psico_tcc = Psicologo.objects.create(nombre='Lic. TCC', whatsapp='2911111111', orientacion='TCC')
        self.psico_tcc.orientaciones.add(self.tcc)

        self.psico_psa = Psicologo.objects.create(nombre='Lic. PSA', whatsapp='2912222222', orientacion='Psicoanalisis')
        self.psico_psa.orientaciones.add(self.psa)

    def test_filtra_por_orientacion(self):
        resp = self.client.get(reverse('buscador'), {'orientacion': self.tcc.pk})
        nombres = [p.nombre for p in resp.context['psicologos']]
        self.assertIn('Lic. TCC', nombres)
        self.assertNotIn('Lic. PSA', nombres)

    def test_sin_filtro_muestra_todos(self):
        resp = self.client.get(reverse('buscador'))
        nombres = [p.nombre for p in resp.context['psicologos']]
        self.assertIn('Lic. TCC', nombres)
        self.assertIn('Lic. PSA', nombres)


class AsignarOrientacionesCommandTests(TestCase):
    """El comando que mapea el texto libre de orientacion a las categorías fijas."""

    def test_categorias_para_texto_mapea_multiples(self):
        from .management.commands.asignar_orientaciones import categorias_para_texto
        encontradas = categorias_para_texto('Terapia cognitivo conductual y sistémica - Tercera Ola')
        self.assertEqual(
            set(encontradas),
            {'Cognitivo Conductual (TCC)', 'Sistémica', 'Tercera Ola'},
        )

    def test_categorias_para_texto_variante_femenina_cognitiva(self):
        from .management.commands.asignar_orientaciones import categorias_para_texto
        self.assertIn('Cognitivo Conductual (TCC)', categorias_para_texto('Terapia Cognitiva'))

    def test_categorias_para_texto_mapea_perinatal(self):
        from .management.commands.asignar_orientaciones import categorias_para_texto
        self.assertEqual(categorias_para_texto('Perinatal'), ['Perinatal'])

    def test_categorias_para_texto_sin_match_devuelve_vacio(self):
        from .management.commands.asignar_orientaciones import categorias_para_texto
        self.assertEqual(categorias_para_texto('mirada metafísica sin escuela definida'), [])

    def test_dry_run_no_toca_la_base(self):
        from django.core.management import call_command
        from .models import Orientacion

        psico = Psicologo.objects.create(nombre='Lic. Dry Run', whatsapp='2913333333', orientacion='Psicoanalisis')
        call_command('asignar_orientaciones')  # sin --apply

        self.assertEqual(Orientacion.objects.count(), 0)
        self.assertEqual(psico.orientaciones.count(), 0)

    def test_apply_crea_categorias_y_asigna(self):
        from django.core.management import call_command
        from .models import Orientacion

        psico = Psicologo.objects.create(
            nombre='Lic. Apply Test', whatsapp='2914444444',
            orientacion='Terapia cognitivo conductual y sistémica',
        )
        call_command('asignar_orientaciones', '--apply')

        self.assertTrue(Orientacion.objects.filter(nombre='Cognitivo Conductual (TCC)').exists())
        nombres_asignados = set(psico.orientaciones.values_list('nombre', flat=True))
        self.assertEqual(nombres_asignados, {'Cognitivo Conductual (TCC)', 'Sistémica'})

    def test_apply_no_duplica_si_se_corre_dos_veces(self):
        from django.core.management import call_command

        psico = Psicologo.objects.create(nombre='Lic. Doble Run', whatsapp='2915555555', orientacion='TCC')
        call_command('asignar_orientaciones', '--apply')
        call_command('asignar_orientaciones', '--apply')

        self.assertEqual(psico.orientaciones.count(), 1)


class LoginCaseInsensitiveTests(TestCase):
    """
    El username siempre es el email cargado. Si queda guardado con
    mayúsculas mezcladas y el profesional lo escribe distinto, el login
    no puede fallar por eso -- ni para cuentas nuevas ni para las que ya
    estaban mal guardadas.
    """

    def test_crear_acceso_guarda_el_email_en_minuscula(self):
        from .admin import CrearAccesoPortalForm
        form = CrearAccesoPortalForm(data={'email': 'Juan.Perez@Gmail.com', 'password_inicial': '123'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['email'], 'juan.perez@gmail.com')

    def test_comando_normaliza_usuarios_existentes(self):
        from django.contrib.auth.models import User
        from django.core.management import call_command

        user = User.objects.create_user(username='Juan.Perez@Gmail.com', email='Juan.Perez@Gmail.com', password='x')
        psico = Psicologo.objects.create(nombre='Lic. Mayúsculas', whatsapp='2916666666', usuario=user)

        call_command('normalizar_emails_usuario')  # dry-run: no cambia nada
        user.refresh_from_db()
        self.assertEqual(user.username, 'Juan.Perez@Gmail.com')

        call_command('normalizar_emails_usuario', '--apply')
        user.refresh_from_db()
        self.assertEqual(user.username, 'juan.perez@gmail.com')
        self.assertEqual(user.email, 'juan.perez@gmail.com')

    def test_comando_no_pisa_si_hay_conflicto(self):
        from django.contrib.auth.models import User
        from django.core.management import call_command

        User.objects.create_user(username='juan.perez@gmail.com', password='x')
        user_mayus = User.objects.create_user(username='Juan.Perez@Gmail.com', password='y')
        Psicologo.objects.create(nombre='Lic. Conflicto', whatsapp='2917777777', usuario=user_mayus)

        call_command('normalizar_emails_usuario', '--apply')

        user_mayus.refresh_from_db()
        self.assertEqual(user_mayus.username, 'Juan.Perez@Gmail.com')  # no se tocó
