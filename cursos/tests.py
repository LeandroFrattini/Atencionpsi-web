import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from profesionales.models import Psicologo

from .models import Curso, InscripcionCurso


def _crear_curso(**extra):
    datos = dict(
        nombre='Taller de prueba', slug='taller-de-prueba', presentador='Lic. Test',
        fecha=datetime.date(2026, 12, 1), hora=datetime.time(10, 0),
        precio_red_consulta=20000, precio_publico=25000, activo=True,
    )
    datos.update(extra)
    return Curso.objects.create(**datos)


class InscripcionPublicaTests(TestCase):
    def setUp(self):
        self.curso = _crear_curso()

    @mock.patch('cursos.views.mercadopago_checkout.crear_preferencia')
    def test_inscripcion_publica_crea_registro_con_precio_publico(self, mock_crear_pref):
        mock_crear_pref.return_value = {'id': 'pref-123', 'init_point': 'https://mp.example/pago'}
        resp = self.client.post(reverse('cursos_inscripcion_publica', args=[self.curso.slug]), {
            'nombre': 'Ana Paciente', 'email': 'ana@example.com', 'whatsapp': '5491111111',
        })
        inscripcion = InscripcionCurso.objects.get()
        self.assertEqual(inscripcion.monto, self.curso.precio_publico)
        self.assertFalse(inscripcion.es_red_consulta)
        self.assertIsNone(inscripcion.psicologo)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, 'https://mp.example/pago')

    def test_curso_agotado_no_deja_inscribirse(self):
        self.curso.cupo_maximo = 1
        self.curso.save()
        InscripcionCurso.objects.create(
            curso=self.curso, nombre='Ya pagó', email='x@example.com', whatsapp='1',
            monto=25000, estado='aprobado',
        )
        resp = self.client.post(reverse('cursos_inscripcion_publica', args=[self.curso.slug]), {
            'nombre': 'Nueva', 'email': 'nueva@example.com', 'whatsapp': '2',
        })
        self.assertEqual(InscripcionCurso.objects.count(), 1)
        self.assertRedirects(resp, reverse('cursos_detalle', args=[self.curso.slug]))


class InscripcionRedConsultaTests(TestCase):
    def setUp(self):
        self.curso = _crear_curso()
        self.usuario = User.objects.create_user('psico@example.com', password='ClaveSegura123', email='psico@example.com')
        self.psico = Psicologo.objects.create(nombre='Lic. Psico', whatsapp='5492222222222', usuario=self.usuario)

    def test_sin_login_pide_iniciar_sesion(self):
        resp = self.client.post(reverse('cursos_inscripcion_red_consulta', args=[self.curso.slug]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('portal_login'), resp.url)

    @mock.patch('cursos.views.mercadopago_checkout.crear_preferencia')
    def test_logueado_usa_precio_de_red_y_sus_propios_datos(self, mock_crear_pref):
        mock_crear_pref.return_value = {'id': 'pref-456', 'init_point': 'https://mp.example/pago'}
        # force_login (no login con password): axes exige un request como
        # argumento de authenticate(), que el login por password del test
        # client no pasa -- mismo motivo que en portal/tests.py.
        self.client.force_login(self.usuario)
        resp = self.client.post(reverse('cursos_inscripcion_red_consulta', args=[self.curso.slug]))
        inscripcion = InscripcionCurso.objects.get()
        self.assertEqual(inscripcion.monto, self.curso.precio_red_consulta)
        self.assertTrue(inscripcion.es_red_consulta)
        self.assertEqual(inscripcion.psicologo, self.psico)
        self.assertEqual(inscripcion.nombre, 'Lic. Psico')
        self.assertEqual(inscripcion.email, 'psico@example.com')
        self.assertEqual(resp.status_code, 302)


class WebhookMercadoPagoTests(TestCase):
    def setUp(self):
        self.curso = _crear_curso()
        self.inscripcion = InscripcionCurso.objects.create(
            curso=self.curso, nombre='Ana', email='ana@example.com', whatsapp='1',
            monto=25000, mp_preference_id='pref-1',
        )

    @mock.patch('cursos.views.mercadopago_checkout.obtener_pago')
    def test_pago_aprobado_confirma_inscripcion_y_manda_mails(self, mock_obtener_pago):
        mock_obtener_pago.return_value = {
            'id': 999, 'status': 'approved', 'external_reference': str(self.inscripcion.pk),
        }
        resp = self.client.post(reverse('cursos_webhook_mercadopago') + '?data.id=999')
        self.assertEqual(resp.status_code, 200)
        self.inscripcion.refresh_from_db()
        self.assertEqual(self.inscripcion.estado, 'aprobado')
        self.assertEqual(self.inscripcion.mp_payment_id, '999')
        self.assertEqual(len(mail.outbox), 2)  # confirmación a la/el inscripta/o + aviso interno

    @mock.patch('cursos.views.mercadopago_checkout.obtener_pago')
    def test_pago_aprobado_dos_veces_no_duplica_el_mail(self, mock_obtener_pago):
        # Mercado Pago puede mandar la misma notificación más de una vez --
        # confirmar de nuevo algo que ya estaba aprobado no tiene que
        # reenviar el mail de confirmación.
        mock_obtener_pago.return_value = {
            'id': 999, 'status': 'approved', 'external_reference': str(self.inscripcion.pk),
        }
        self.client.post(reverse('cursos_webhook_mercadopago') + '?data.id=999')
        self.client.post(reverse('cursos_webhook_mercadopago') + '?data.id=999')
        self.assertEqual(len(mail.outbox), 2)

    @mock.patch('cursos.views.mercadopago_checkout.obtener_pago')
    def test_pago_rechazado_marca_estado_sin_mandar_mail(self, mock_obtener_pago):
        mock_obtener_pago.return_value = {
            'id': 998, 'status': 'rejected', 'external_reference': str(self.inscripcion.pk),
        }
        self.client.post(reverse('cursos_webhook_mercadopago') + '?data.id=998')
        self.inscripcion.refresh_from_db()
        self.assertEqual(self.inscripcion.estado, 'rechazado')
        self.assertEqual(len(mail.outbox), 0)

    def test_notificacion_sin_id_no_rompe(self):
        # Un JSON válido pero sin data.id (ej. una notificación de otro tipo,
        # como merchant_order) no es un error -- simplemente no hay nada
        # para hacer con esa notificación puntual.
        resp = self.client.post(reverse('cursos_webhook_mercadopago'), data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)

    def test_notificacion_con_body_no_json_da_400_en_vez_de_reventar(self):
        resp = self.client.post(reverse('cursos_webhook_mercadopago'), data='esto no es json', content_type='application/json')
        self.assertEqual(resp.status_code, 400)


class SimularPagoDevTests(TestCase):
    def setUp(self):
        self.curso = _crear_curso()
        self.inscripcion = InscripcionCurso.objects.create(
            curso=self.curso, nombre='Ana', email='ana@example.com', whatsapp='1', monto=25000,
        )

    def test_simular_pago_aprobado_en_debug(self):
        with self.settings(DEBUG=True):
            resp = self.client.post(reverse('cursos_simular_pago', args=[self.inscripcion.pk]), {'accion': 'aprobar'})
        self.inscripcion.refresh_from_db()
        self.assertEqual(self.inscripcion.estado, 'aprobado')
        self.assertRedirects(resp, reverse('cursos_resultado', args=[self.inscripcion.pk]))

    def test_simular_pago_no_existe_fuera_de_debug(self):
        with self.settings(DEBUG=False):
            resp = self.client.post(reverse('cursos_simular_pago', args=[self.inscripcion.pk]), {'accion': 'aprobar'})
        self.assertEqual(resp.status_code, 404)


class CursoModelTests(TestCase):
    def test_cupos_disponibles_sin_limite_es_none(self):
        curso = _crear_curso(cupo_maximo=None)
        self.assertIsNone(curso.cupos_disponibles)
        self.assertFalse(curso.agotado)

    def test_cupos_disponibles_descuenta_solo_aprobados(self):
        curso = _crear_curso(cupo_maximo=2)
        InscripcionCurso.objects.create(curso=curso, nombre='A', email='a@example.com', whatsapp='1', monto=1, estado='aprobado')
        InscripcionCurso.objects.create(curso=curso, nombre='B', email='b@example.com', whatsapp='2', monto=1, estado='pendiente')
        self.assertEqual(curso.cupos_disponibles, 1)
        self.assertFalse(curso.agotado)


class FormacionListadoTests(TestCase):
    def test_lista_solo_cursos_activos_y_futuros(self):
        _crear_curso(slug='vigente', nombre='Curso Vigente', fecha=datetime.date(2099, 1, 1), activo=True)
        _crear_curso(slug='inactivo', nombre='Curso Inactivo', fecha=datetime.date(2099, 1, 1), activo=False)
        _crear_curso(slug='vencido', nombre='Curso Vencido', fecha=datetime.date(2000, 1, 1), activo=True)
        resp = self.client.get(reverse('formacion'))
        self.assertContains(resp, 'Curso Vigente')
        self.assertNotContains(resp, 'Curso Inactivo')
        self.assertNotContains(resp, 'Curso Vencido')
        self.assertEqual(resp.context['cursos_activos'].count(), 1)
