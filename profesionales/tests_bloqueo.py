"""Bloqueo de IPs desde el admin: quien está bloqueado no entra al sitio (ni lee los números de WhatsApp)."""
import datetime

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import bloqueo
from .models import IPBloqueada, Psicologo

NAVEGADOR = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Mobile Safari/537.36'
MALA = '190.9.9.9'


def _desde(ip, **extra):
    return dict(HTTP_CF_CONNECTING_IP=ip, HTTP_USER_AGENT=NAVEGADOR, **extra)


class NormalizarTests(TestCase):
    def test_acepta_ips_y_rangos(self):
        self.assertEqual(bloqueo.normalizar(' 190.1.2.3 '), '190.1.2.3')
        self.assertEqual(bloqueo.normalizar('190.1.2.77/24'), '190.1.2.0/24')
        self.assertEqual(bloqueo.normalizar('2800:150:1::1'), '2800:150:1::1')

    def test_rechaza_lo_que_no_es_una_ip(self):
        for malo in ('', 'hola', '190.1.2', '190.1.2.3.4', '999.1.1.1'):
            with self.assertRaises(ValueError, msg=malo):
                bloqueo.normalizar(malo)

    def test_rechaza_ips_internas_para_no_bloquear_a_render(self):
        for interna in ('10.25.198.215', '192.168.0.1', '172.16.5.5', '127.0.0.1', '169.254.1.1', '0.0.0.0'):
            with self.assertRaises(ValueError, msg=interna):
                bloqueo.normalizar(interna)

    def test_rechaza_rangos_enormes(self):
        for grande in ('190.0.0.0/8', '190.1.0.0/15', '2800::/16'):
            with self.assertRaises(ValueError, msg=grande):
                bloqueo.normalizar(grande)
        self.assertEqual(bloqueo.normalizar('190.1.0.0/16'), '190.1.0.0/16')

    def test_el_modelo_tambien_lo_valida(self):
        with self.assertRaises(ValidationError):
            IPBloqueada(ip='10.0.0.1').full_clean()
        with self.assertRaises(ValidationError):
            IPBloqueada.objects.create(ip='10.0.0.1')


class BloqueoDelSitioTests(TestCase):
    def setUp(self):
        self.psico = Psicologo.objects.create(nombre='Lic. Prueba', whatsapp='2911234567', activo=True)

    def bloquear(self, ip=MALA, **extra):
        return IPBloqueada.objects.create(ip=ip, **extra)

    def test_quien_no_esta_bloqueado_entra_normal(self):
        self.bloquear()
        self.assertEqual(self.client.get(reverse('buscador'), **_desde('190.1.1.1')).status_code, 200)
        self.assertEqual(self.client.get(reverse('buscador')).status_code, 200)

    def test_la_ip_bloqueada_recibe_403_en_todo_el_sitio_y_no_ve_los_numeros(self):
        self.bloquear()
        for url in (reverse('inicio'), reverse('buscador'), reverse('perfil_psicologo', args=[self.psico.slug]), '/cualquier-cosa/'):
            resp = self.client.get(url, **_desde(MALA))
            self.assertEqual(resp.status_code, 403, url)
            self.assertNotContains(resp, 'wa.me', status_code=403)
        self.assertContains(self.client.get(reverse('buscador'), **_desde(MALA)), 'Acceso restringido', status_code=403)

    def test_tampoco_puede_contar_clicks(self):
        self.bloquear()
        resp = self.client.post(reverse('registrar_click_whatsapp', args=[self.psico.slug]), **_desde(MALA))
        self.assertEqual(resp.status_code, 403)

    def test_el_bloqueo_rige_apenas_se_guarda_y_se_levanta_al_borrar(self):
        self.assertEqual(self.client.get(reverse('buscador'), **_desde(MALA)).status_code, 200)
        regla = self.bloquear()
        self.assertEqual(self.client.get(reverse('buscador'), **_desde(MALA)).status_code, 403)
        regla.delete()
        self.assertEqual(self.client.get(reverse('buscador'), **_desde(MALA)).status_code, 200)

    def test_destildar_o_vencer_levanta_el_bloqueo(self):
        regla = self.bloquear()
        regla.activa = False
        regla.save()
        self.assertEqual(self.client.get(reverse('buscador'), **_desde(MALA)).status_code, 200)
        regla.activa, regla.hasta = True, timezone.now() - datetime.timedelta(minutes=1)
        regla.save()
        self.assertEqual(self.client.get(reverse('buscador'), **_desde(MALA)).status_code, 200)
        regla.hasta = timezone.now() + datetime.timedelta(days=1)
        regla.save()
        self.assertEqual(self.client.get(reverse('buscador'), **_desde(MALA)).status_code, 403)

    def test_un_rango_bloquea_a_todas_sus_ips(self):
        self.bloquear('190.9.9.0/24')
        self.assertEqual(self.client.get(reverse('buscador'), **_desde('190.9.9.200')).status_code, 403)
        self.assertEqual(self.client.get(reverse('buscador'), **_desde('190.9.10.1')).status_code, 200)

    def test_no_se_puede_esquivar_agregando_una_ip_falsa_a_x_forwarded_for(self):
        self.bloquear()
        resp = self.client.get(reverse('buscador'), HTTP_USER_AGENT=NAVEGADOR, HTTP_X_FORWARDED_FOR=f'8.8.8.8, {MALA}')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.get(reverse('buscador'), HTTP_USER_AGENT=NAVEGADOR, HTTP_X_FORWARDED_FOR=f'{MALA}, 8.8.8.8')
        self.assertEqual(resp.status_code, 403)

    def test_x_forwarded_for_de_un_tercero_solo_afecta_su_propio_pedido(self):
        self.bloquear()
        self.client.get(reverse('buscador'), HTTP_X_FORWARDED_FOR=MALA)
        self.assertEqual(self.client.get(reverse('buscador'), **_desde('190.1.1.1')).status_code, 200)

    def test_el_admin_nunca_se_bloquea(self):
        self.bloquear()
        self.assertEqual(self.client.get('/admin/login/', **_desde(MALA)).status_code, 200)

    def test_las_ips_internas_de_render_no_bloquean_a_nadie(self):
        self.bloquear()
        resp = self.client.get(reverse('buscador'), HTTP_USER_AGENT=NAVEGADOR, REMOTE_ADDR='10.25.198.215',
                               HTTP_X_FORWARDED_FOR='190.1.1.1, 10.25.9.82')
        self.assertEqual(resp.status_code, 200)

    def test_si_la_lista_falla_el_sitio_sigue_funcionando(self):
        from unittest import mock
        with mock.patch('profesionales.bloqueo._redes_bloqueadas', side_effect=Exception('base caída')):
            self.assertEqual(self.client.get(reverse('buscador'), **_desde(MALA)).status_code, 200)

    def test_queda_en_el_log(self):
        self.bloquear()
        with self.assertLogs('clicks.whatsapp', level='INFO') as registro:
            self.client.get(reverse('buscador'), **_desde(MALA))
        self.assertIn(f'IP-BLOQUEADA ip={MALA}', registro.output[0])


class IPsBloqueadasDeEntradaTests(TestCase):
    """Las dos IPs que recorrían a los profesionales vienen cargadas por la migración."""

    def test_vienen_bloqueadas(self):
        for ip in ('142.249.120.173', '181.239.167.157'):
            self.assertTrue(bloqueo.esta_bloqueada(ip), ip)
        self.assertFalse(bloqueo.esta_bloqueada('190.1.1.1'))

    def test_la_de_la_red_de_celulares_vence_a_los_7_dias_y_la_otra_no(self):
        claro = IPBloqueada.objects.get(ip='181.239.167.157')
        lumen = IPBloqueada.objects.get(ip='142.249.120.173')
        self.assertIsNone(lumen.hasta)
        dias = (claro.hasta - timezone.now()).total_seconds() / 86400
        self.assertTrue(6.9 < dias <= 7.01, dias)

    def test_estan_bloqueadas_en_el_sitio(self):
        self.assertEqual(self.client.get(reverse('buscador'), **_desde('142.249.120.173')).status_code, 403)
        self.assertEqual(self.client.get(reverse('buscador'), **_desde('181.239.167.157')).status_code, 403)


class BloquearDesdeElAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin@example.com', password='ClaveSegura123')
        self.client.force_login(self.admin)
        self.url = reverse('admin:bloquear_ip')

    def bloquear(self, ip, **extra):
        return self.client.post(self.url, {'ip': ip, 'horas': 24, **extra}, **_desde('190.1.1.1'))

    def test_el_boton_bloquea_y_vuelve_al_resumen(self):
        resp = self.bloquear(MALA, motivo='Recorría la lista')
        self.assertRedirects(resp, reverse('admin:clicks_por_ip') + '?horas=24')
        self.assertTrue(IPBloqueada.objects.filter(ip=MALA, activa=True, motivo='Recorría la lista').exists())
        self.assertTrue(bloqueo.esta_bloqueada(MALA))

    def test_bloquear_dos_veces_no_duplica_y_reactiva(self):
        self.bloquear(MALA)
        IPBloqueada.objects.filter(ip=MALA).update(activa=False)
        bloqueo.invalidar()
        self.bloquear(MALA)
        self.assertEqual(IPBloqueada.objects.filter(ip=MALA).count(), 1)
        self.assertTrue(IPBloqueada.objects.get(ip=MALA).activa)

    def test_no_deja_bloquear_la_propia_conexion(self):
        resp = self.client.post(self.url, {'ip': '190.1.1.1'}, **_desde('190.1.1.1'), follow=True)
        self.assertFalse(IPBloqueada.objects.filter(ip='190.1.1.1').exists())
        self.assertContains(resp, 'tu propia conexión')

    def test_no_deja_bloquear_ips_internas_ni_basura(self):
        for malo in ('10.25.198.215', 'hola', '190.0.0.0/8', ''):
            self.bloquear(malo)
        self.assertFalse(IPBloqueada.objects.filter(ip__in=('10.25.198.215', 'hola', '190.0.0.0/8')).exists())

    def test_por_get_no_hace_nada(self):
        resp = self.client.get(self.url + f'?ip={MALA}')
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(IPBloqueada.objects.filter(ip=MALA).exists())

    def test_solo_el_equipo_con_permiso(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {'ip': MALA}).status_code, 302)
        empleado = User.objects.create_user('staff@example.com', password='ClaveSegura123', is_staff=True)
        self.client.force_login(empleado)
        self.assertEqual(self.client.post(self.url, {'ip': MALA}).status_code, 403)
        self.assertFalse(IPBloqueada.objects.filter(ip=MALA).exists())

    def test_el_resumen_muestra_el_boton_o_el_estado(self):
        from .models import ClickWhatsAppDetalle
        psico = Psicologo.objects.create(nombre='Lic. Prueba', whatsapp='2911234567', activo=True)
        for ip in (MALA, '190.2.2.2'):
            ClickWhatsAppDetalle.objects.create(psicologo=psico, ip=ip)
        IPBloqueada.objects.create(ip=MALA)
        resp = self.client.get(reverse('admin:clicks_por_ip'))
        filas = {f['ip']: f for f in resp.context['por_ip']}
        self.assertTrue(filas[MALA]['bloqueada'])
        self.assertFalse(filas['190.2.2.2']['bloqueada'])
        self.assertContains(resp, 'Bloqueada')
        self.assertContains(resp, 'name="ip" value="190.2.2.2"')

    def test_la_lista_de_ips_bloqueadas_esta_en_el_admin(self):
        self.assertEqual(self.client.get(reverse('admin:profesionales_ipbloqueada_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:profesionales_ipbloqueada_add')).status_code, 200)
