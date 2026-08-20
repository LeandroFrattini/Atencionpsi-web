import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from profesionales.models import Psicologo
from portal.models import Gasto, Pago, Paciente, Turno


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
        # tampoco se creó ningún turno "copia" para el paciente de B
        self.assertFalse(Turno.objects.filter(paciente=self.paciente_b, psicologo=self.psico_a).exists())

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

    def test_reagendar_crea_turno_nuevo_y_no_toca_el_original(self):
        """
        "Reagendar" arma la sesión de la semana que viene sin borrar el
        registro de la sesión original (por ejemplo, un turno ya marcado
        como realizado con sus notas de la sesión de hoy).
        """
        fecha_original = timezone.now()
        turno_a = Turno.objects.create(
            psicologo=self.psico_a, paciente=self.paciente_a, fecha_hora=fecha_original,
            estado='realizado', notas_sesion='buena sesión de hoy',
        )
        url = reverse('portal_turno_reagendar_rapido', args=[turno_a.pk])
        resp = self.client_a.post(url, {})
        self.assertRedirects(resp, reverse('portal_dashboard'))

        turno_a.refresh_from_db()
        self.assertEqual(turno_a.fecha_hora, fecha_original)  # el original no se mueve
        self.assertEqual(turno_a.estado, 'realizado')
        self.assertEqual(turno_a.notas_sesion, 'buena sesión de hoy')
        self.assertFalse(turno_a.reagendado)

        nuevo = Turno.objects.exclude(pk=turno_a.pk).get(paciente=self.paciente_a)
        self.assertEqual(nuevo.fecha_hora, fecha_original + datetime.timedelta(weeks=1))
        self.assertEqual(nuevo.estado, 'agendado')
        self.assertTrue(nuevo.reagendado)

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

    def test_no_puede_mover_turno_de_otro_psicologo(self):
        fecha_original = self.turno_b.fecha_hora
        url = reverse('portal_turno_mover', args=[self.turno_b.pk])
        resp = self.client_a.post(url, {'hora': '15', 'minuto': '30'})
        self.assertEqual(resp.status_code, 404)
        self.turno_b.refresh_from_db()
        self.assertEqual(self.turno_b.fecha_hora, fecha_original)

    def test_puede_mover_su_propio_turno_arrastrando_dentro_del_dia(self):
        fecha_original = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        turno_a = Turno.objects.create(
            psicologo=self.psico_a, paciente=self.paciente_a, fecha_hora=fecha_original,
        )
        url = reverse('portal_turno_mover', args=[turno_a.pk])
        resp = self.client_a.post(url, {'hora': '15', 'minuto': '30'})
        self.assertRedirects(resp, reverse('portal_dashboard'))
        turno_a.refresh_from_db()
        local = timezone.localtime(turno_a.fecha_hora)
        self.assertEqual((local.hour, local.minute), (15, 30))
        self.assertEqual(local.date(), timezone.localtime(fecha_original).date())
        self.assertTrue(turno_a.reagendado)

    def test_puede_mover_su_propio_turno_a_otro_dia(self):
        """Arrastrar el turno hasta el selector de días lo cambia de fecha."""
        fecha_original = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        turno_a = Turno.objects.create(
            psicologo=self.psico_a, paciente=self.paciente_a, fecha_hora=fecha_original,
        )
        otro_dia = (timezone.localtime(fecha_original) + datetime.timedelta(days=2)).date()
        url = reverse('portal_turno_mover', args=[turno_a.pk])
        resp = self.client_a.post(url, {'hora': '10', 'minuto': '0', 'fecha': otro_dia.isoformat()})
        self.assertRedirects(resp, reverse('portal_dashboard'))
        turno_a.refresh_from_db()
        local = timezone.localtime(turno_a.fecha_hora)
        self.assertEqual(local.date(), otro_dia)
        self.assertEqual((local.hour, local.minute), (10, 0))

    def test_no_puede_mover_turno_de_otro_psicologo_a_otro_dia(self):
        fecha_original = self.turno_b.fecha_hora
        otro_dia = (timezone.localtime(fecha_original) + datetime.timedelta(days=2)).date()
        url = reverse('portal_turno_mover', args=[self.turno_b.pk])
        resp = self.client_a.post(url, {'hora': '10', 'minuto': '0', 'fecha': otro_dia.isoformat()})
        self.assertEqual(resp.status_code, 404)
        self.turno_b.refresh_from_db()
        self.assertEqual(self.turno_b.fecha_hora, fecha_original)


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


class PortalAdminDashboardTests(TestCase):
    """
    Cuenta superuser sin Psicologo asociado (la dueña del sitio): en vez de
    romper, tiene que caer en su propio panel general con estadísticas de
    todos los profesionales y el alta/baja del buscador.
    """

    def setUp(self):
        self.superuser = User.objects.create_superuser('duena_test', 'duena@example.com', 'ClaveDuenaSegura2026')
        self.user_psico = User.objects.create_user('psico_normal', password='ClaveDePrueba123')
        self.psico = Psicologo.objects.create(nombre='Psicólogo Normal', whatsapp='3333333333', usuario=self.user_psico)

        self.client_super = Client()
        self.client_super.force_login(self.superuser)
        self.client_psico = Client()
        self.client_psico.force_login(self.user_psico)

    def test_superuser_sin_psicologo_no_rompe_al_entrar_al_portal(self):
        resp = self.client_super.get(reverse('portal_dashboard'), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'portal/admin_dashboard.html')

    def test_superuser_ve_estadisticas_generales_no_privadas(self):
        """
        El panel general solo muestra conteos agregados (cuántos pacientes en
        toda la red, cuántos profesionales con agenda activa) -- NO datos de
        turnos por profesional (atendidos/cancelados/sin cobrar), porque eso
        es privado de cada psicólogo con sus pacientes.
        """
        Paciente.objects.create(psicologo=self.psico, nombre='P', apellido='A')
        Paciente.objects.create(psicologo=self.psico, nombre='Q', apellido='B')

        psico_sin_agenda = Psicologo.objects.create(nombre='Psicólogo Sin Agenda', whatsapp='9999999999')

        resp = self.client_super.get(reverse('portal_admin_agenda'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['stats']['total_pacientes'], 2)
        self.assertEqual(resp.context['stats']['total_con_agenda'], 1)  # solo self.psico tiene usuario
        self.assertNotIn('atendidos', resp.context['stats'])
        self.assertNotIn('cancelados', resp.context['stats'])
        self.assertNotIn('sin_cobrar', resp.context['stats'])
        self.assertNotContains(resp, 'Atendidos')
        self.assertNotContains(resp, 'Sin cobrar')

    def test_panel_general_muestra_cantidad_de_pacientes_por_psicologo(self):
        """
        Al lado del nombre de cada profesional, la dueña ve entre paréntesis
        cuántos pacientes tiene cargados -- solo en este panel, no en el
        buscador ni en la vista propia del profesional.
        """
        Paciente.objects.create(psicologo=self.psico, nombre='P', apellido='A')
        Paciente.objects.create(psicologo=self.psico, nombre='Q', apellido='B')
        psico_sin_pacientes = Psicologo.objects.create(nombre='Psicólogo Sin Pacientes', whatsapp='9999999999')

        resp = self.client_super.get(reverse('portal_admin_agenda'))
        self.assertEqual(resp.status_code, 200)

        por_pk = {
            p.pk: p.cantidad_pacientes
            for p in list(resp.context['pagina_con']) + list(resp.context['pagina_sin'])
        }
        self.assertEqual(por_pk[self.psico.pk], 2)
        self.assertEqual(por_pk[psico_sin_pacientes.pk], 0)
        self.assertContains(resp, '(2)')
        self.assertContains(resp, '(0)')

    def test_psicologo_normal_no_puede_entrar_al_panel_general(self):
        resp = self.client_psico.get(reverse('portal_admin_dashboard'), follow=True)
        self.assertTemplateNotUsed(resp, 'portal/admin_dashboard.html')

        # El panel general está en tres páginas separadas (bienvenida, agenda
        # y finanzas) -- un psicólogo común no puede entrar a ninguna.
        resp = self.client_psico.get(reverse('portal_admin_agenda'), follow=True)
        self.assertTemplateNotUsed(resp, 'portal/admin_agenda.html')
        resp = self.client_psico.get(reverse('portal_admin_finanzas'), follow=True)
        self.assertTemplateNotUsed(resp, 'portal/admin_finanzas.html')

    def test_superuser_puede_dar_de_baja_y_alta(self):
        self.assertTrue(self.psico.activo)
        url = reverse('portal_psicologo_toggle', args=[self.psico.pk])

        resp = self.client_super.post(url)
        self.assertEqual(resp.status_code, 302)
        self.psico.refresh_from_db()
        self.assertFalse(self.psico.activo)

        self.client_super.post(url)
        self.psico.refresh_from_db()
        self.assertTrue(self.psico.activo)

    def test_psicologo_normal_no_puede_dar_de_baja_a_nadie(self):
        url = reverse('portal_psicologo_toggle', args=[self.psico.pk])
        self.client_psico.post(url)
        self.psico.refresh_from_db()
        self.assertTrue(self.psico.activo)  # no cambió
        self.assertFalse(self.psico.usuario.is_superuser)

    def test_superuser_puede_crear_acceso_a_psicologo_sin_usuario(self):
        sin_acceso = Psicologo.objects.create(nombre='Sin Acceso', whatsapp='4444444444')
        url = reverse('portal_psicologo_crear_acceso', args=[sin_acceso.pk])
        resp = self.client_super.post(url, {'email': 'nueva@example.com', 'password_inicial': '4444444444'})
        self.assertEqual(resp.status_code, 302)

        sin_acceso.refresh_from_db()
        self.assertIsNotNone(sin_acceso.usuario)
        self.assertEqual(sin_acceso.usuario.username, 'nueva@example.com')
        self.assertTrue(sin_acceso.usuario.check_password('4444444444'))
        self.assertTrue(sin_acceso.debe_cambiar_password)
        self.assertFalse(sin_acceso.usuario.is_staff)
        self.assertFalse(sin_acceso.usuario.is_superuser)

    def test_no_deja_crear_acceso_con_email_repetido(self):
        sin_acceso = Psicologo.objects.create(nombre='Sin Acceso Dos', whatsapp='5555555555')
        url = reverse('portal_psicologo_crear_acceso', args=[sin_acceso.pk])
        resp = self.client_super.post(url, {'email': 'psico_normal', 'password_inicial': '5555555555'})
        self.assertEqual(resp.status_code, 200)  # vuelve a mostrar el form con el error
        sin_acceso.refresh_from_db()
        self.assertIsNone(sin_acceso.usuario)

    def test_psicologo_normal_no_puede_crear_accesos(self):
        sin_acceso = Psicologo.objects.create(nombre='Sin Acceso Tres', whatsapp='6666666666')
        url = reverse('portal_psicologo_crear_acceso', args=[sin_acceso.pk])
        self.client_psico.post(url, {'email': 'colada@example.com', 'password_inicial': '6666666666'})
        sin_acceso.refresh_from_db()
        self.assertIsNone(sin_acceso.usuario)

    def test_superuser_puede_blanquear_password(self):
        self.user_psico.set_password('LoQueSeaMenosSuWhatsapp')
        self.user_psico.save()
        self.psico.debe_cambiar_password = False
        self.psico.save(update_fields=['debe_cambiar_password'])

        url = reverse('portal_psicologo_blanquear_password', args=[self.psico.pk])
        resp = self.client_super.post(url)
        self.assertEqual(resp.status_code, 302)

        self.psico.refresh_from_db()
        self.user_psico.refresh_from_db()
        self.assertTrue(self.user_psico.check_password(self.psico.whatsapp_limpio()))
        self.assertTrue(self.psico.debe_cambiar_password)

    def test_blanquear_password_sin_usuario_no_rompe(self):
        sin_acceso = Psicologo.objects.create(nombre='Sin Acceso Cuatro', whatsapp='7777777777')
        url = reverse('portal_psicologo_blanquear_password', args=[sin_acceso.pk])
        resp = self.client_super.post(url)
        self.assertEqual(resp.status_code, 302)

    def test_finanzas_es_pagina_aparte_y_solo_la_ve_el_superuser(self):
        Pago.objects.create(psicologo=self.psico, fecha=timezone.localdate(), monto=1000)
        Gasto.objects.create(fecha=timezone.localdate(), monto=300)

        resp = self.client_psico.get(reverse('portal_admin_finanzas'), follow=True)
        self.assertTemplateNotUsed(resp, 'portal/admin_finanzas.html')

        resp = self.client_super.get(reverse('portal_admin_finanzas'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_ingresos'], 1000)
        self.assertEqual(resp.context['total_egresos'], 300)
        self.assertEqual(resp.context['ganancia_total'], 700)


class IngresoPortalTests(TestCase):
    """El login de un profesional al portal queda registrado (uno por día);
    el login de la dueña del sitio (superuser sin Psicologo) no cuenta."""

    def setUp(self):
        self.user_psico = User.objects.create_user('psico_ingreso_test', password='ClaveDePrueba123')
        self.psico = Psicologo.objects.create(nombre='Psicólogo Ingreso', whatsapp='8888888888', usuario=self.user_psico)
        self.superuser = User.objects.create_superuser('duena_ingreso_test', 'd@example.com', 'ClaveDuenaSegura2026')

    def test_login_de_psicologo_queda_registrado(self):
        # force_login (no login con password) porque axes exige un request
        # real en authenticate(), que el helper login() no provee -- mismo
        # motivo que en PortalScopingTests. force_login sigue disparando la
        # señal user_logged_in igual, así que sirve para probar esto.
        from .models import IngresoPortal
        self.assertEqual(IngresoPortal.objects.count(), 0)

        self.client.force_login(self.user_psico)

        self.assertEqual(IngresoPortal.objects.count(), 1)
        ingreso = IngresoPortal.objects.first()
        self.assertEqual(ingreso.psicologo, self.psico)
        self.assertEqual(ingreso.fecha, timezone.localdate())
        self.assertEqual(ingreso.cantidad, 1)

    def test_dos_logins_el_mismo_dia_suman_uno_solo_pero_cuentan_cantidad(self):
        from .models import IngresoPortal
        self.client.force_login(self.user_psico)
        self.client.logout()
        self.client.force_login(self.user_psico)

        self.assertEqual(IngresoPortal.objects.count(), 1)  # una sola fila para hoy
        self.assertEqual(IngresoPortal.objects.first().cantidad, 2)  # pero se contaron los 2 ingresos

    def test_login_de_superuser_no_se_cuenta(self):
        from .models import IngresoPortal
        self.client.force_login(self.superuser)
        self.assertEqual(IngresoPortal.objects.count(), 0)

    def test_panel_general_muestra_ingresos_de_hoy(self):
        client_super = Client()
        client_super.force_login(self.superuser)

        self.client.force_login(self.user_psico)

        resp = client_super.get(reverse('portal_admin_agenda'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['stats']['ingresos_hoy'], 1)

        dias = resp.context['ultimos_7_dias']
        self.assertEqual(len(dias), 7)
        self.assertTrue(dias[-1]['es_hoy'])
        self.assertEqual(dias[-1]['cantidad'], 1)


class LoginCaseInsensitiveEndToEndTests(TestCase):
    """
    Login real (por POST, no force_login) para probar el flujo completo:
    el username queda guardado con mayúsculas mezcladas, pero el
    profesional lo escribe en minúscula (o al revés) y el login tiene
    que funcionar igual.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='Juan.Perez@Gmail.com', password='ClaveDePrueba123')
        Psicologo.objects.create(nombre='Lic. Juan Perez', whatsapp='2918888888', usuario=self.user)

    def test_login_funciona_con_otra_capitalizacion(self):
        resp = self.client.post(reverse('portal_login'), {
            'username': 'juan.perez@gmail.com',  # todo en minúscula, distinto a como está guardado
            'password': 'ClaveDePrueba123',
        })
        self.assertRedirects(resp, reverse('portal_dashboard'))

    def test_login_sigue_funcionando_tal_cual_estaba_guardado(self):
        resp = self.client.post(reverse('portal_login'), {
            'username': 'Juan.Perez@Gmail.com',
            'password': 'ClaveDePrueba123',
        })
        self.assertRedirects(resp, reverse('portal_dashboard'))

    def test_login_funciona_en_mayuscula_total_sin_correr_ningun_comando(self):
        # A propósito NO corre normalizar_emails_usuario acá -- el arreglo
        # tiene que andar solo, sin depender de un paso manual previo.
        resp = self.client.post(reverse('portal_login'), {
            'username': 'JUAN.PEREZ@GMAIL.COM',
            'password': 'ClaveDePrueba123',
        })
        self.assertRedirects(resp, reverse('portal_dashboard'))

    def test_login_con_password_incorrecta_sigue_fallando(self):
        resp = self.client.post(reverse('portal_login'), {
            'username': 'juan.perez@gmail.com',
            'password': 'ClaveIncorrecta',
        })
        self.assertEqual(resp.status_code, 200)  # vuelve al form, no te deja entrar
