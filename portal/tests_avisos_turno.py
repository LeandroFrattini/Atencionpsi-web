"""Mail de aviso al profesional cuando un paciente reserva desde la web: sale, y si no sale queda a la vista."""
import datetime
import smtplib
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.models import Paciente, Turno
from profesionales.models import Psicologo


class _Base(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('sofia', email='sofia@example.com', password='ClaveDePrueba123')
        self.psi = Psicologo.objects.create(
            nombre='Sofía Duarte', slug='sofia-duarte', whatsapp='1111111111', activo=True, usuario=self.usuario,
        )
        self.paciente = Paciente.objects.create(
            psicologo=self.psi, nombre='Martina', apellido='Alonso', email='martina@example.com', telefono='11 5555 1234',
        )

    def turno(self, **extra):
        datos = dict(psicologo=self.psi, paciente=self.paciente, fecha_hora=timezone.now() + datetime.timedelta(days=2),
                     modalidad='virtual', origen='publico')
        datos.update(extra)
        return Turno.objects.create(**datos)

    def reservar_desde_la_web(self):
        manana = (timezone.localdate() + datetime.timedelta(days=2))
        with mock.patch('profesionales.views.slot_disponible', return_value=(True, 'virtual')):
            return self.client.post(reverse('reservar_confirmar', args=[self.psi.slug]), {
                'fecha': manana.isoformat(), 'hora': '17:00', 'nombre': 'Martina', 'apellido': 'Alonso',
                'email': 'otra@example.com', 'telefono': '11 5555 1234', 'fecha_nacimiento': '1996-03-14',
            })


class EnvioDelAvisoTests(_Base):
    def test_una_reserva_desde_la_web_le_avisa_al_profesional_con_copia_interna_y_lo_anota(self):
        resp = self.reservar_desde_la_web()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['sofia@example.com'])
        self.assertIn('Nuevo turno', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].bcc, ['atencionpsi.ar@gmail.com'])
        turno = Turno.objects.get(paciente__email='otra@example.com')
        self.assertIsNotNone(turno.aviso_enviado_en)
        self.assertEqual(turno.aviso_error, '')

    def test_si_el_envio_falla_el_paciente_igual_ve_su_reserva_y_queda_el_motivo(self):
        falla = smtplib.SMTPAuthenticationError(535, b'Authentication failed')
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=falla):
            with self.assertLogs('portal.notificaciones', level='ERROR'):
                resp = self.reservar_desde_la_web()
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'reserva_confirmada.html')
        turno = Turno.objects.get(paciente__email='otra@example.com')
        self.assertIsNone(turno.aviso_enviado_en)
        self.assertIn('SMTPAuthenticationError', turno.aviso_error)
        self.assertIn('535', turno.aviso_error)

    def test_si_el_profesional_no_tiene_mail_el_aviso_va_a_la_copia_interna(self):
        User.objects.filter(pk=self.usuario.pk).update(email='')
        self.psi.refresh_from_db()
        turno = self.turno()
        self.assertTrue(self.intentar(turno))
        self.assertEqual([m.to for m in mail.outbox], [['atencionpsi.ar@gmail.com']])
        self.assertIn('no tiene mail cargado', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].bcc, [])   # no se repite a sí misma
        turno.refresh_from_db()
        self.assertIsNotNone(turno.aviso_enviado_en)
        self.assertIn('copia interna', turno.aviso_error)

    @override_settings(TURNOS_BCC_EMAIL='')
    def test_sin_mail_del_profesional_ni_copia_interna_queda_anotado_que_no_se_aviso_a_nadie(self):
        User.objects.filter(pk=self.usuario.pk).update(email='')
        turno = self.turno()
        self.assertFalse(self.intentar(turno))
        self.assertEqual(mail.outbox, [])
        turno.refresh_from_db()
        self.assertIsNone(turno.aviso_enviado_en)
        self.assertIn('no se avisó a nadie', turno.aviso_error)

    def intentar(self, turno):
        from portal.notificaciones import intentar_aviso_nuevo_turno
        return intentar_aviso_nuevo_turno(Turno.objects.select_related('psicologo__usuario', 'paciente').get(pk=turno.pk))


class AdminTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser('admin', 'admin@example.com', 'ClaveDePrueba123'))
        self.lista = reverse('admin:portal_turno_changelist')

    def test_la_lista_muestra_si_el_aviso_salio_o_por_que_no(self):
        ok = self.turno()
        Turno.objects.filter(pk=ok.pk).update(aviso_enviado_en=timezone.now())
        mal = self.turno(fecha_hora=timezone.now() + datetime.timedelta(days=3))
        Turno.objects.filter(pk=mal.pk).update(aviso_error='SMTPAuthenticationError: (535, b"Authentication failed")')
        resp = self.client.get(self.lista)
        self.assertContains(resp, '✔')
        self.assertContains(resp, 'no salió: SMTPAuthenticationError')

    def test_el_filtro_separa_enviados_con_error_y_sin_registro(self):
        ok = self.turno()
        Turno.objects.filter(pk=ok.pk).update(aviso_enviado_en=timezone.now())
        mal = self.turno(fecha_hora=timezone.now() + datetime.timedelta(days=3))
        Turno.objects.filter(pk=mal.pk).update(aviso_error='Boom')
        viejo = self.turno(fecha_hora=timezone.now() + datetime.timedelta(days=4))
        for valor, esperado in (('enviado', ok), ('error', mal), ('sin_registro', viejo)):
            ids = {t.pk for t in self.client.get(self.lista, {'aviso': valor}).context['cl'].result_list}
            self.assertEqual(ids, {esperado.pk}, valor)

    def test_la_accion_reenvia_el_aviso_y_actualiza_la_constancia(self):
        turno = self.turno()
        Turno.objects.filter(pk=turno.pk).update(aviso_error='SMTPServerDisconnected: caído')
        resp = self.client.post(self.lista, {'action': 'reenviar_aviso_action', '_selected_action': [turno.pk]}, follow=True)
        self.assertContains(resp, 'Se reenvió el aviso de 1 turno')
        self.assertEqual(mail.outbox[0].to, ['sofia@example.com'])
        turno.refresh_from_db()
        self.assertIsNotNone(turno.aviso_enviado_en)
        self.assertEqual(turno.aviso_error, '')

    def test_la_accion_dice_si_el_reenvio_vuelve_a_fallar(self):
        turno = self.turno()
        with mock.patch('django.core.mail.message.EmailMessage.send', side_effect=OSError('sin red')):
            with self.assertLogs('portal.notificaciones', level='ERROR'):
                resp = self.client.post(self.lista, {'action': 'reenviar_aviso_action', '_selected_action': [turno.pk]}, follow=True)
        self.assertContains(resp, 'no salieron')
        turno.refresh_from_db()
        self.assertIn('OSError: sin red', turno.aviso_error)

    def test_el_inicio_del_admin_avisa_si_hay_reservas_con_el_aviso_sin_enviar(self):
        self.assertNotContains(self.client.get(reverse('admin:index')), 'SIN enviar')
        turno = self.turno()
        Turno.objects.filter(pk=turno.pk).update(aviso_error='Boom')
        resp = self.client.get(reverse('admin:index'))
        self.assertContains(resp, '1 reserva(s) de la web con el aviso al profesional SIN enviar')
        self.assertContains(resp, 'aviso=error')

    def test_el_inicio_tiene_el_boton_para_probar_el_envio(self):
        self.assertContains(self.client.get(reverse('admin:index')), 'Probar el envío de mails de turnos')


class ProbarMailTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser('admin', 'admin@example.com', 'ClaveDePrueba123'))
        self.url = reverse('admin:portal_turno_probar_mail')

    def test_solo_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_si_sale_lo_dice_y_manda_un_mail_de_prueba_a_la_copia_interna(self):
        resp = self.client.post(self.url, follow=True)
        self.assertContains(resp, 'Salió el mail de prueba a atencionpsi.ar@gmail.com')
        self.assertEqual(mail.outbox[0].to, ['atencionpsi.ar@gmail.com'])
        self.assertTrue(mail.outbox[0].subject.startswith('[PRUEBA]'))

    def test_si_falla_muestra_el_error_exacto_y_si_estan_cargadas_las_credenciales(self):
        with override_settings(EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD=''):
            with mock.patch('django.core.mail.message.EmailMessage.send',
                            side_effect=smtplib.SMTPAuthenticationError(535, b'Authentication failed')):
                resp = self.client.post(self.url, follow=True)
        self.assertContains(resp, 'El mail de prueba NO salió: SMTPAuthenticationError')
        self.assertContains(resp, 'Usuario de Brevo cargado: NO')
        self.assertContains(resp, 'Clave de Brevo cargada: NO')

    def test_hay_que_ser_staff(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
