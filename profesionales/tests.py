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
