"""Origen de cada click en el botón de WhatsApp (IP real, navegador y anuncio) y el resumen por IP del admin."""
import datetime
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from . import origen_clicks
from .models import ClickWhatsApp, ClickWhatsAppDetalle, Psicologo

NAVEGADOR = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Mobile Safari/537.36'
GCLID = 'Cj0KCQiA_ejemplo'
REFERER = f'https://atencionpsi.com.ar/buscador/?gad_source=1&gclid={GCLID}'


def _psico(n=1):
    return Psicologo.objects.create(nombre=f'Lic. Prueba {n}', whatsapp=f'29112345{n:02d}', activo=True)


class IpRealTests(TestCase):
    def ip(self, **meta):
        return origen_clicks.ip_real(SimpleNamespace(META=meta))

    def test_prefiere_el_encabezado_del_proxy_con_la_ip_del_visitante(self):
        self.assertEqual(self.ip(HTTP_CF_CONNECTING_IP='190.1.2.3', HTTP_X_FORWARDED_FOR='8.8.8.8', REMOTE_ADDR='10.0.0.1'), '190.1.2.3')
        self.assertEqual(self.ip(HTTP_TRUE_CLIENT_IP='190.1.2.4', REMOTE_ADDR='10.0.0.1'), '190.1.2.4')
        self.assertEqual(self.ip(HTTP_X_REAL_IP='190.1.2.5', REMOTE_ADDR='10.0.0.1'), '190.1.2.5')

    def test_sin_esos_usa_la_primera_ip_publica_de_x_forwarded_for(self):
        self.assertEqual(self.ip(HTTP_X_FORWARDED_FOR='190.5.6.7, 10.25.9.82', REMOTE_ADDR='10.25.198.215'), '190.5.6.7')

    def test_ignora_las_ips_internas(self):
        self.assertEqual(self.ip(HTTP_X_FORWARDED_FOR='10.1.1.1, 192.168.0.4, 172.16.3.3, 201.1.1.1', REMOTE_ADDR='10.0.0.1'), '201.1.1.1')
        self.assertEqual(self.ip(HTTP_CF_CONNECTING_IP='10.0.0.9', REMOTE_ADDR='10.0.0.1'), '10.0.0.1')

    def test_valores_raros_no_rompen(self):
        self.assertEqual(self.ip(HTTP_X_FORWARDED_FOR='basura, ,', REMOTE_ADDR='10.0.0.1'), '10.0.0.1')
        self.assertEqual(self.ip(), '')

    def test_acepta_ipv6(self):
        self.assertEqual(self.ip(HTTP_X_FORWARDED_FOR='2800:150:1::1'), '2800:150:1::1')

    def test_el_gclid_sale_del_referer(self):
        self.assertEqual(origen_clicks.gclid_del_referer(REFERER), GCLID)
        self.assertEqual(origen_clicks.gclid_del_referer('https://x.com/?gbraid=ABC'), 'ABC')
        self.assertEqual(origen_clicks.gclid_del_referer('https://atencionpsi.com.ar/buscador/'), '')
        self.assertEqual(origen_clicks.gclid_del_referer(''), '')
        self.assertEqual(origen_clicks.gclid_del_referer(None), '')

    def test_las_cabeceras_se_guardan_tal_cual(self):
        texto = origen_clicks.cabeceras_crudas(SimpleNamespace(META={
            'REMOTE_ADDR': '10.0.0.1', 'HTTP_X_FORWARDED_FOR': '190.1.1.1, 10.2.2.2'}))
        self.assertEqual(texto, 'REMOTE_ADDR=10.0.0.1 | X-Forwarded-For=190.1.1.1, 10.2.2.2')


class RegistroDelClickTests(TestCase):
    def click(self, psico, **extra):
        defecto = dict(HTTP_USER_AGENT=NAVEGADOR, HTTP_REFERER=REFERER, REMOTE_ADDR='10.25.198.215')
        defecto.update(extra)
        return self.client.post(reverse('registrar_click_whatsapp', args=[psico.slug]), **defecto)

    def test_guarda_ip_navegador_y_anuncio_y_sigue_contando(self):
        psico = _psico()
        resp = self.click(psico, HTTP_X_FORWARDED_FOR='190.5.6.7, 10.25.9.82')
        self.assertEqual(resp.json(), {'ok': True})
        detalle = ClickWhatsAppDetalle.objects.get()
        self.assertEqual((detalle.ip, detalle.gclid, detalle.psicologo), ('190.5.6.7', GCLID, psico))
        self.assertEqual(detalle.user_agent, NAVEGADOR)
        self.assertIn('X-Forwarded-For=190.5.6.7', detalle.cabeceras)
        self.assertEqual(ClickWhatsApp.objects.get().cantidad, 1)

    def test_los_bots_no_se_registran(self):
        psico = _psico()
        for agente in ('Googlebot/2.1 (+http://www.google.com/bot.html)', 'WhatsApp/2.23.20.0', ''):
            self.click(psico, HTTP_USER_AGENT=agente)
        self.assertEqual(ClickWhatsAppDetalle.objects.count(), 0)

    def test_si_falla_guardar_el_origen_el_click_igual_cuenta(self):
        psico = _psico()
        with mock.patch('profesionales.views.origen_clicks.registrar_click', side_effect=Exception('base caída')):
            resp = self.click(psico)
        self.assertEqual(resp.json(), {'ok': True})
        self.assertEqual(ClickWhatsApp.objects.get().cantidad, 1)

    def test_queda_en_el_log_con_la_ip(self):
        psico = _psico()
        with self.assertLogs('clicks.whatsapp', level='INFO') as registro:
            self.click(psico, HTTP_CF_CONNECTING_IP='190.9.9.9')
        self.assertIn('ip=190.9.9.9', registro.output[0])
        self.assertIn(psico.slug, registro.output[0])

    def test_los_numeros_y_botones_siguen_en_la_pagina(self):
        """Este registro no cambia lo que ve el visitante: el WhatsApp sigue en el HTML."""
        psico = _psico()
        for url in (reverse('buscador'), reverse('perfil_psicologo', args=[psico.slug])):
            contenido = self.client.get(url).content.decode()
            self.assertIn(f'https://wa.me/{psico.whatsapp_limpio()}', contenido, url)

    def test_se_borran_los_detalles_de_mas_de_30_dias(self):
        psico = _psico()
        viejo = ClickWhatsAppDetalle.objects.create(psicologo=psico, ip='1.1.1.1')
        reciente = ClickWhatsAppDetalle.objects.create(psicologo=psico, ip='2.2.2.2')
        ClickWhatsAppDetalle.objects.filter(pk=viejo.pk).update(creado=timezone.now() - datetime.timedelta(days=31))
        self.assertEqual(origen_clicks.purgar_antiguos(), 1)
        self.assertEqual(list(ClickWhatsAppDetalle.objects.all()), [reciente])


class ResumenPorIpEnElAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin@example.com', password='ClaveSegura123')
        self.client.force_login(self.admin)

    def cargar(self, ip, cuantos, gclid=''):
        for n in range(1, cuantos + 1):
            ClickWhatsAppDetalle.objects.create(psicologo=Psicologo.objects.get_or_create(
                nombre=f'Lic. Prueba {n}', defaults={'whatsapp': f'29112345{n:02d}', 'activo': True})[0], ip=ip, gclid=gclid,
                user_agent=NAVEGADOR)

    def test_pone_arriba_a_quien_recorrio_mas_profesionales_y_lo_marca(self):
        self.cargar('190.1.1.1', 2)
        self.cargar('201.9.9.9', 9, gclid=GCLID)
        resp = self.client.get(reverse('admin:clicks_por_ip'))
        self.assertEqual(resp.status_code, 200)
        filas = resp.context['por_ip']
        self.assertEqual([f['ip'] for f in filas], ['201.9.9.9', '190.1.1.1'])
        self.assertTrue(filas[0]['sospechosa'])
        self.assertFalse(filas[1]['sospechosa'])
        self.assertEqual(filas[0]['profesionales'], 9)
        self.assertContains(resp, '201.9.9.9')
        self.assertContains(resp, 'cx-alerta')

    def test_agrupa_por_anuncio(self):
        self.cargar('201.9.9.9', 7, gclid=GCLID)
        self.cargar('201.9.9.8', 3, gclid=GCLID)
        fila = self.client.get(reverse('admin:clicks_por_ip')).context['por_anuncio'][0]
        self.assertEqual((fila['gclid'], fila['clicks'], fila['profesionales'], fila['ips']), (GCLID, 10, 7, 2))
        self.assertTrue(fila['sospechoso'])

    def test_el_periodo_filtra_y_un_valor_raro_vuelve_a_24_horas(self):
        self.cargar('190.1.1.1', 2)
        ClickWhatsAppDetalle.objects.update(creado=timezone.now() - datetime.timedelta(hours=5))
        self.assertEqual(self.client.get(reverse('admin:clicks_por_ip') + '?horas=1').context['total'], 0)
        self.assertEqual(self.client.get(reverse('admin:clicks_por_ip') + '?horas=6').context['total'], 2)
        self.assertEqual(self.client.get(reverse('admin:clicks_por_ip') + '?horas=999').context['horas'], 24)
        self.assertEqual(self.client.get(reverse('admin:clicks_por_ip') + '?horas=abc').context['horas'], 24)

    def test_sin_datos_no_rompe(self):
        self.assertEqual(self.client.get(reverse('admin:clicks_por_ip')).status_code, 200)

    def test_solo_lo_ve_el_equipo(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('admin:clicks_por_ip')).status_code, 302)
        comun = User.objects.create_user('comun@example.com', password='ClaveSegura123')
        self.client.force_login(comun)
        self.assertEqual(self.client.get(reverse('admin:clicks_por_ip')).status_code, 302)

    def test_la_lista_tiene_el_boton_al_resumen_y_es_de_solo_lectura(self):
        self.cargar('190.1.1.1', 1)
        resp = self.client.get(reverse('admin:profesionales_clickwhatsappdetalle_changelist'))
        self.assertContains(resp, reverse('admin:clicks_por_ip'))
        self.assertEqual(self.client.get(reverse('admin:profesionales_clickwhatsappdetalle_add')).status_code, 403)
