import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from profesionales.models import Psicologo
from portal.models import Paciente, Turno


class PortalScopingTests(TestCase):
    """
    Verifica que un psicólogo NUNCA pueda ver ni editar los pacientes/turnos
    de otro, aunque adivine o modifique el id en la URL (IDOR).
    """

    def setUp(self):
        self.user_a = User.objects.create_user('psico_a', password='ClaveDePrueba123')
        self.user_b = User.objects.create_user('psico_b', password='ClaveDePrueba123')

        self.psico_a = Psicologo.objects.create(nombre='Psicóloga A', whatsapp='1111111111', usuario=self.user_a)
        self.psico_b = Psicologo.objects.create(nombre='Psicólogo B', whatsapp='2222222222', usuario=self.user_b)

        self.paciente_a = Paciente.objects.create(psicologo=self.psico_a, nombre='PacienteDeA', apellido='Apellido')
        self.paciente_b = Paciente.objects.create(psicologo=self.psico_b, nombre='PacienteDeB', apellido='Apellido')

        self.turno_b = Turno.objects.create(
            psicologo=self.psico_b, paciente=self.paciente_b, fecha_hora=timezone.now()
        )

        # force_login evita pasar por el backend de autenticación (axes exige
        # un `request` real en authenticate(), que el helper login() no provee).
        self.client_a = Client()
        self.client_a.force_login(self.user_a)

    def test_no_puede_ver_paciente_de_otro_psicologo(self):
        url = reverse('portal_paciente_detalle', args=[self.paciente_b.pk])
        resp = self.client_a.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_puede_ver_su_propio_paciente(self):
        url = reverse('portal_paciente_detalle', args=[self.paciente_a.pk])
        resp = self.client_a.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_no_puede_editar_paciente_de_otro_psicologo(self):
        url = reverse('portal_paciente_editar', args=[self.paciente_b.pk])
        resp = self.client_a.post(url, {
            'nombre': 'Hackeado', 'apellido': 'Apellido', 'activo': 'on',
        })
        self.assertEqual(resp.status_code, 404)
        self.paciente_b.refresh_from_db()
        self.assertEqual(self.paciente_b.nombre, 'PacienteDeB')  # no se modificó

    def test_no_puede_ver_turno_de_otro_psicologo(self):
        url = reverse('portal_turno_editar', args=[self.turno_b.pk])
        resp = self.client_a.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_no_puede_crear_turno_para_paciente_de_otro_psicologo(self):
        """
        Aunque el psicólogo A mande a mano el id del paciente de B en el POST,
        el queryset del form (restringido a sus propios pacientes) lo rechaza.
        """
        url = reverse('portal_turno_nuevo')
        resp = self.client_a.post(url, {
            'paciente': self.paciente_b.pk,
            'fecha_hora': '2027-01-01T10:00',
            'estado': 'agendado',
        })
        self.assertEqual(resp.status_code, 200)  # vuelve a mostrar el form con error
        self.assertFalse(Turno.objects.filter(paciente=self.paciente_b, psicologo=self.psico_a).exists())

    def test_lista_de_pacientes_no_incluye_los_de_otro_psicologo(self):
        url = reverse('portal_pacientes')
        resp = self.client_a.get(url)
        self.assertEqual(resp.status_code, 200)
        pacientes_mostrados = list(resp.context['pacientes'])
        self.assertIn(self.paciente_a, pacientes_mostrados)
        self.assertNotIn(self.paciente_b, pacientes_mostrados)

    def test_anonimo_es_redirigido_al_login(self):
        client = Client()
        url = reverse('portal_dashboard')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('portal_login'), resp.url)

    def test_no_puede_marcar_realizado_turno_de_otro_psicologo(self):
        url = reverse('portal_turno_marcar_realizado', args=[self.turno_b.pk])
        resp = self.client_a.post(url, {'notas_sesion': 'intento ajeno'})
        self.assertEqual(resp.status_code, 404)
        self.turno_b.refresh_from_db()
        self.assertEqual(self.turno_b.estado, 'agendado')
        self.assertEqual(self.turno_b.notas_sesion, '')

    def test_no_puede_reagendar_turno_de_otro_psicologo(self):
        fecha_original = self.turno_b.fecha_hora
        url = reverse('portal_turno_reagendar_rapido', args=[self.turno_b.pk])
        resp = self.client_a.post(url, {})
        self.assertEqual(resp.status_code, 404)
        self.turno_b.refresh_from_db()
        self.assertEqual(self.turno_b.fecha_hora, fecha_original)
        self.assertFalse(self.turno_b.reagendado)

    def test_puede_marcar_su_propio_turno_como_realizado_con_comentario(self):
        turno_a = Turno.objects.create(
            psicologo=self.psico_a, paciente=self.paciente_a, fecha_hora=timezone.now()
        )
        url = reverse('portal_turno_marcar_realizado', args=[turno_a.pk])
        resp = self.client_a.post(url, {'notas_sesion': 'buena evolución'})
        self.assertRedirects(resp, reverse('portal_dashboard'))
        turno_a.refresh_from_db()
        self.assertEqual(turno_a.estado, 'realizado')
        self.assertEqual(turno_a.notas_sesion, 'buena evolución')

    def test_puede_reagendar_su_propio_turno_una_semana_despues(self):
        fecha_original = timezone.now()
        turno_a = Turno.objects.create(
            psicologo=self.psico_a, paciente=self.paciente_a, fecha_hora=fecha_original
        )
        url = reverse('portal_turno_reagendar_rapido', args=[turno_a.pk])
        resp = self.client_a.post(url, {})
        self.assertRedirects(resp, reverse('portal_dashboard'))
        turno_a.refresh_from_db()
        self.assertEqual(turno_a.fecha_hora, fecha_original + datetime.timedelta(weeks=1))
        self.assertTrue(turno_a.reagendado)
        self.assertEqual(turno_a.estado, 'agendado')

    def test_marcar_realizado_sin_pago_queda_pendiente_de_cobro(self):
        turno_a = Turno.objects.create(
            psicologo=self.psico_a, paciente=self.paciente_a, fecha_hora=timezone.now()
        )
        url = reverse('portal_turno_marcar_realizado', args=[turno_a.pk])
        resp = self.client_a.post(url, {'pagado': '0'})
        self.assertRedirects(resp, reverse('portal_dashboard'))
        turno_a.refresh_from_db()
        self.assertEqual(turno_a.estado, 'realizado')
        self.assertFalse(turno_a.pagado)

    def test_marcar_realizado_con_pago_1(self):
        turno_a = Turno.objects.create(
            psicologo=self.psico_a, paciente=self.paciente_a, fecha_hora=timezone.now()
        )
        url = reverse('portal_turno_marcar_realizado', args=[turno_a.pk])
        resp = self.client_a.post(url, {'pagado': '1'})
        self.assertRedirects(resp, reverse('portal_dashboard'))
        turno_a.refresh_from_db()
        self.assertTrue(turno_a.pagado)

    def test_no_puede_marcar_pagado_turno_de_otro_psicologo(self):
        url = reverse('portal_turno_marcar_pagado', args=[self.turno_b.pk])
        resp = self.client_a.post(url, {})
        self.assertEqual(resp.status_code, 404)
        self.turno_b.refresh_from_db()
        self.assertFalse(self.turno_b.pagado)

    def test_puede_marcar_su_propio_turno_como_pagado(self):
        turno_a = Turno.objects.create(
            psicologo=self.psico_a, paciente=self.paciente_a, fecha_hora=timezone.now(),
            estado='realizado', pagado=False,
        )
        url = reverse('portal_turno_marcar_pagado', args=[turno_a.pk])
        resp = self.client_a.post(url, {})
        self.assertRedirects(resp, reverse('portal_dashboard'))
        turno_a.refresh_from_db()
        self.assertTrue(turno_a.pagado)


class CambioPasswordObligatorioTests(TestCase):
    """
    Un psicólogo con contraseña provisoria (debe_cambiar_password=True) no
    debe poder ver NINGUNA otra pantalla del portal hasta cambiarla.
    """

    def setUp(self):
        self.user = User.objects.create_user('psico_nuevo', password='2915551234')
        self.psico = Psicologo.objects.create(
            nombre='Psicólogo Nuevo', whatsapp='2915551234',
            usuario=self.user, debe_cambiar_password=True,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_dashboard_redirige_a_cambiar_password(self):
        resp = self.client.get(reverse('portal_dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('portal_cambiar_password'), resp.url)

    def test_puede_completar_cambio_de_password(self):
        resp = self.client.post(reverse('portal_cambiar_password'), {
            'old_password': '2915551234',
            'new_password1': 'UnaClaveMuchoMasFuerte2026',
            'new_password2': 'UnaClaveMuchoMasFuerte2026',
        })
        self.assertRedirects(resp, reverse('portal_dashboard'))
        self.psico.refresh_from_db()
        self.assertFalse(self.psico.debe_cambiar_password)

        # ahora sí puede entrar al dashboard sin que lo rebote
        resp2 = self.client.get(reverse('portal_dashboard'))
        self.assertEqual(resp2.status_code, 200)


class CrearAccesoPortalAdminActionTests(TestCase):
    """La acción de admin que da de alta el acceso de un psicólogo nuevo."""

    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin_test', 'admin@example.com', 'ClaveAdminSegura2026')
        self.psico = Psicologo.objects.create(nombre='Psicólogo Nuevo', whatsapp='2915551234')
        self.client = Client()
        self.client.force_login(self.admin_user)

    def test_crea_usuario_con_password_provisoria(self):
        url = reverse('admin:profesionales_psicologo_changelist')
        resp = self.client.post(url, {
            'action': 'crear_acceso_portal_action',
            '_selected_action': [self.psico.pk],
            'apply': '1',
            'email': 'nuevo.psicologo@example.com',
            'password_inicial': '2915551234',
        })
        self.assertEqual(resp.status_code, 302)

        self.psico.refresh_from_db()
        self.assertTrue(self.psico.debe_cambiar_password)
        self.assertIsNotNone(self.psico.usuario)
        self.assertEqual(self.psico.usuario.username, 'nuevo.psicologo@example.com')
        self.assertTrue(self.psico.usuario.check_password('2915551234'))
        self.assertFalse(self.psico.usuario.is_staff)
        self.assertFalse(self.psico.usuario.is_superuser)
