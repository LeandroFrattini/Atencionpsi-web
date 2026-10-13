import zipfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db.models import Model as DjangoModel
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from portal.models import Pago

from .generador_imagenes import generar_imagen_feed, generar_imagen_story
from .models import FOTO_LADO_MAXIMO, Ciudad, Modalidad, Psicologo, Publico


def _jpeg_bytes(ancho, alto, color=(180, 140, 120)):
    buf = BytesIO()
    Image.new('RGB', (ancho, alto), color).save(buf, 'JPEG', quality=95)
    return buf.getvalue()


def _foto_subida(ancho, alto, nombre='foto.jpg'):
    return SimpleUploadedFile(nombre, _jpeg_bytes(ancho, alto), content_type='image/jpeg')


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


class GeneradorImagenFeedTests(TestCase):
    """Post de feed (2026-09-22): sin foto/orientación/ciudad no debe
    romper, y con contenido largo el 'a quién atiende' se achica solo
    (mismo criterio que la historia)."""

    def setUp(self):
        self.psico = Psicologo.objects.create(
            nombre='Lic. Prueba Genérica', whatsapp='2911234567', orientacion='Psicoanálisis',
        )
        self.psico.modalidades.set([Modalidad.objects.create(nombre='Presencial')])
        self.psico.destinatarios.set([Publico.objects.create(nombre='Adultos')])

    def test_genera_imagen_del_tamano_correcto(self):
        img = generar_imagen_feed(self.psico)
        self.assertEqual(img.size, (1080, 1350))
        self.assertEqual(img.mode, 'RGB')

    def test_sin_foto_ni_orientacion_ni_ciudad_no_rompe(self):
        vacio = Psicologo.objects.create(nombre='Lic. Sin Datos', whatsapp='2911234567')
        img = generar_imagen_feed(vacio)
        self.assertEqual(img.size, (1080, 1350))

    def test_atiende_a_largo_no_se_corta(self):
        todos = list(Publico.objects.all()) + [
            Publico.objects.create(nombre='Familias'),
            Publico.objects.create(nombre='Parejas'),
            Publico.objects.create(nombre='Orientación Vocacional'),
            Publico.objects.create(nombre='Orientación a Padres'),
        ]
        self.psico.destinatarios.set(todos)
        img = generar_imagen_feed(self.psico)  # no debe lanzar excepción
        self.assertEqual(img.size, (1080, 1350))


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

    def test_descarga_zip_con_el_post_de_feed(self):
        url = reverse('admin:profesionales_psicologo_changelist')
        resp = self.client.post(url, {
            'action': 'generar_imagen_feed_action',
            '_selected_action': [self.psico.pk],
            'apply': '1',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/zip')
        zf = zipfile.ZipFile(BytesIO(resp.content))
        nombres = zf.namelist()
        self.assertEqual(len(nombres), 1)
        self.assertTrue(nombres[0].endswith('_feed.jpg'))


class FotoOptimizadaTests(TestCase):
    """
    _foto_optimizada() se dispara sola desde Psicologo.save() para
    cualquier foto NUEVA (ver el guard de _committed ahí) -- estos tests
    prueban ese camino real (crear con una foto grande) en vez de llamar
    a la función interna directo.
    """

    def test_foto_grande_se_achica_al_lado_maximo(self):
        psico = Psicologo.objects.create(
            nombre='Lic. Foto Grande', whatsapp='2911111120',
            foto=_foto_subida(3000, 2000),
        )
        with Image.open(psico.foto) as img:
            self.assertLessEqual(max(img.size), FOTO_LADO_MAXIMO)
            # Se mantiene la proporción 3:2 original.
            self.assertAlmostEqual(img.size[0] / img.size[1], 3000 / 2000, places=2)

    def test_foto_chica_no_se_toca(self):
        original = _jpeg_bytes(400, 400)
        psico = Psicologo.objects.create(
            nombre='Lic. Foto Chica', whatsapp='2911111121',
            foto=SimpleUploadedFile('chica.jpg', original, content_type='image/jpeg'),
        )
        psico.foto.seek(0)
        self.assertEqual(psico.foto.read(), original)

    def test_resave_sin_tocar_la_foto_no_la_reprocesa(self):
        """Guardar de nuevo por otro motivo (p.ej. update_fields=['destacado'])
        no debe volver a pasar la foto ya guardada por el optimizador."""
        psico = Psicologo.objects.create(
            nombre='Lic. Resave', whatsapp='2911111122',
            foto=_foto_subida(3000, 2000),
        )
        nombre_archivo_procesado = psico.foto.name
        psico.destacado = True
        psico.save(update_fields=['destacado'])
        self.assertEqual(psico.foto.name, nombre_archivo_procesado)


class OptimizarFotosCommandTests(TestCase):
    def setUp(self):
        self.grande = Psicologo.objects.create(nombre='Lic. Sin Optimizar', whatsapp='2911111123')
        # foto.save(save=False) + Model.save() (el de Django, no el
        # override de Psicologo) para dejar la foto grande tal cual en el
        # storage, sin que Psicologo.save() la procese sola -- así se
        # simula una foto vieja, subida antes de que existiera el resize
        # automático.
        self.grande.foto.save('vieja.jpg', ContentFile(_jpeg_bytes(3000, 2000)), save=False)
        DjangoModel.save(self.grande, update_fields=['foto'])

    def test_dry_run_no_toca_nada(self):
        nombre_antes = self.grande.foto.name
        call_command('optimizar_fotos')
        self.grande.refresh_from_db()
        self.assertEqual(self.grande.foto.name, nombre_antes)
        with Image.open(self.grande.foto) as img:
            self.assertGreater(max(img.size), FOTO_LADO_MAXIMO)

    def test_apply_achica_la_foto_vieja(self):
        call_command('optimizar_fotos', apply=True)
        self.grande.refresh_from_db()
        with Image.open(self.grande.foto) as img:
            self.assertLessEqual(max(img.size), FOTO_LADO_MAXIMO)

    def test_apply_no_rompe_con_profesional_sin_foto(self):
        Psicologo.objects.create(nombre='Lic. Sin Foto', whatsapp='2911111124')
        call_command('optimizar_fotos', apply=True)  # no debe tirar excepción

    def test_foto_ya_del_tamano_correcto_se_refresca_con_el_mismo_nombre_y_contenido(self):
        """Una foto que no necesita achicarse igual se resube (mismo nombre,
        mismo contenido) para que le quede el Cache-Control nuevo -- antes
        el comando la salteaba del todo y se quedaba con el cache viejo."""
        chica = Psicologo.objects.create(nombre='Lic. Ya Optimizada', whatsapp='2911111125')
        datos_originales = _jpeg_bytes(400, 400)
        chica.foto.save('chica.jpg', ContentFile(datos_originales), save=False)
        DjangoModel.save(chica, update_fields=['foto'])
        nombre_antes = chica.foto.name

        call_command('optimizar_fotos', apply=True)

        chica.refresh_from_db()
        self.assertEqual(chica.foto.name, nombre_antes)  # mismo nombre, no un duplicado
        chica.foto.seek(0)
        self.assertEqual(chica.foto.read(), datos_originales)  # mismo contenido


class MarcarPagoMesAdminActionTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin_pago_test', 'admin@example.com', 'ClaveAdminSegura2026')
        self.client = Client()
        self.client.force_login(self.admin_user)
        self.changelist_url = reverse('admin:profesionales_psicologo_changelist')

    def _post(self, psicologos, apply=False):
        data = {'action': 'marcar_pago_mes_action', '_selected_action': [p.pk for p in psicologos]}
        if apply:
            data['apply'] = '1'
        return self.client.post(self.changelist_url, data)

    def test_pantalla_de_confirmacion_separa_a_quien_se_le_va_a_cobrar(self):
        con_monto = Psicologo.objects.create(nombre='Con Monto', whatsapp='2911111111', monto_pagado=25000)
        sin_monto = Psicologo.objects.create(nombre='Sin Monto', whatsapp='2911111112')
        resp = self._post([con_monto, sin_monto])
        self.assertEqual(resp.status_code, 200)
        self.assertIn(con_monto, resp.context['a_marcar'])
        self.assertIn(sin_monto, resp.context['sin_monto'])
        # Todavía no se tocó la base -- recién se crea el Pago al confirmar.
        self.assertEqual(Pago.objects.count(), 0)

    def test_confirmar_crea_el_pago_con_el_monto_cargado(self):
        psico = Psicologo.objects.create(nombre='Lic. Cobrable', whatsapp='2911111113', monto_pagado=18000)
        resp = self._post([psico], apply=True)
        self.assertEqual(resp.status_code, 302)
        pago = Pago.objects.get(psicologo=psico)
        self.assertEqual(pago.monto, 18000)
        self.assertIn('Mensualidad', pago.concepto)
        self.assertEqual(pago.fecha, timezone.localdate())

    def test_sin_monto_pagado_no_crea_nada(self):
        psico = Psicologo.objects.create(nombre='Lic. Sin Monto', whatsapp='2911111114')
        self._post([psico], apply=True)
        self.assertEqual(Pago.objects.filter(psicologo=psico).count(), 0)

    def test_no_duplica_si_ya_tiene_un_pago_de_este_mes(self):
        psico = Psicologo.objects.create(nombre='Lic. Ya Pagó', whatsapp='2911111115', monto_pagado=20000)
        Pago.objects.create(
            psicologo=psico, fecha=timezone.localdate(), monto=20000,
            concepto='Mensualidad cargada a mano',
        )
        self._post([psico], apply=True)
        # Sigue habiendo un solo Pago -- no se duplicó.
        self.assertEqual(Pago.objects.filter(psicologo=psico).count(), 1)

    def test_columna_pago_mes_actual_en_el_listado(self):
        pagado = Psicologo.objects.create(nombre='Lic. Al Día', whatsapp='2911111116', monto_pagado=15000)
        Pago.objects.create(psicologo=pagado, fecha=timezone.localdate(), monto=15000, concepto='Mensualidad septiembre')
        sin_pagar = Psicologo.objects.create(nombre='Lic. Debe', whatsapp='2911111117', monto_pagado=15000)
        resp = self.client.get(self.changelist_url)
        contenido = resp.content.decode('utf-8')
        # No hay una forma directa de mapear la fila a la celda sin parsear
        # HTML de más -- alcanza con confirmar que aparece al menos un ✅
        # (el pagado) y que el que debe sigue listado en la página.
        self.assertIn('✅', contenido)
        self.assertIn('Lic. Debe', contenido)

    def test_filtro_pago_mes_separa_pagados_de_no_pagados(self):
        pagado = Psicologo.objects.create(nombre='Lic. Filtro Sí', whatsapp='2911111118', monto_pagado=15000)
        Pago.objects.create(psicologo=pagado, fecha=timezone.localdate(), monto=15000, concepto='Mensualidad septiembre')
        no_pagado = Psicologo.objects.create(nombre='Lic. Filtro No', whatsapp='2911111119')

        resp_si = self.client.get(self.changelist_url, {'pago_mes': 'si'})
        self.assertIn(pagado, resp_si.context['cl'].queryset)
        self.assertNotIn(no_pagado, resp_si.context['cl'].queryset)

        resp_no = self.client.get(self.changelist_url, {'pago_mes': 'no'})
        self.assertIn(no_pagado, resp_no.context['cl'].queryset)
        self.assertNotIn(pagado, resp_no.context['cl'].queryset)


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


class BuscadorPorNombreTests(TestCase):
    def setUp(self):
        Psicologo.objects.create(nombre='Lic. Oriana Casazza', whatsapp='2911111111', activo=True)
        Psicologo.objects.create(nombre='Lic. Barbara Pereyra', whatsapp='2912222222', activo=True)
        self.client = Client()

    def test_busca_por_nombre_de_pila(self):
        resp = self.client.get(reverse('buscador'), {'nombre': 'oriana'})
        nombres = [p.nombre for p in resp.context['psicologos']]
        self.assertIn('Lic. Oriana Casazza', nombres)
        self.assertNotIn('Lic. Barbara Pereyra', nombres)

    def test_busca_por_apellido_sin_importar_mayusculas(self):
        resp = self.client.get(reverse('buscador'), {'nombre': 'PEREYRA'})
        nombres = [p.nombre for p in resp.context['psicologos']]
        self.assertIn('Lic. Barbara Pereyra', nombres)
        self.assertNotIn('Lic. Oriana Casazza', nombres)

    def test_sin_texto_muestra_todos(self):
        resp = self.client.get(reverse('buscador'), {'nombre': ''})
        self.assertEqual(len(resp.context['psicologos']), 2)

    def test_texto_sin_coincidencias_no_rompe(self):
        resp = self.client.get(reverse('buscador'), {'nombre': 'zzz-nadie-se-llama-asi'})
        self.assertEqual(len(resp.context['psicologos']), 0)


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


class BotonTurnosReservadosEnHomeAdminTests(TestCase):
    """Botón agregado 2026-09-24: acceso rápido desde /admin/ a los turnos
    reservados por pacientes desde la web (origen='publico'), más recientes
    primero -- para chequear de un vistazo si están entrando reservas."""

    def setUp(self):
        self.admin_user = User.objects.create_superuser('admin_home_test', 'admin@example.com', 'ClaveAdminSegura2026')
        self.client = Client()
        self.client.force_login(self.admin_user)

    def test_el_boton_aparece_en_el_home_del_admin_con_el_link_correcto(self):
        resp = self.client.get(reverse('admin:index'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Turnos reservados desde la web')
        url_esperada = reverse('admin:portal_turno_changelist') + '?origen__exact=publico&o=-6'
        self.assertContains(resp, url_esperada)


class ApiDestacadosTests(TestCase):
    """Listado público que lee atencionpsi.lat para su mix de destacados."""

    def _psi(self, nombre, slug, **extra):
        datos = dict(nombre=nombre, slug=slug, whatsapp='5492915000000', foto='psicologos/a.jpg', activo=True)
        datos.update(extra)
        return Psicologo.objects.create(**datos)

    def test_devuelve_solo_datos_publicos(self):
        p = self._psi('Ana Beltrán', 'ana-beltran', orientacion='Gestalt')
        p.ciudades.add(Ciudad.objects.create(nombre='Bahía Blanca'))
        resp = self.client.get(reverse('api_destacados'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json')
        fila = resp.json()['profesionales'][0]
        self.assertEqual(set(fila), {'nombre', 'ciudad', 'orientacion', 'foto', 'url'})
        self.assertEqual(fila['nombre'], 'Ana Beltrán')
        self.assertEqual(fila['ciudad'], 'Bahía Blanca')
        self.assertEqual(fila['orientacion'], 'Gestalt')
        self.assertTrue(fila['url'].startswith('https://') and fila['url'].endswith('/psicologo/ana-beltran/'))
        self.assertNotIn('5492915000000', resp.content.decode())   # nunca el WhatsApp

    def test_no_incluye_inactivos_ni_sin_foto(self):
        self._psi('Activa', 'activa')
        self._psi('Inactiva', 'inactiva', activo=False)
        self._psi('Sin foto', 'sin-foto', foto='')
        nombres = [f['nombre'] for f in self.client.get(reverse('api_destacados')).json()['profesionales']]
        self.assertEqual(nombres, ['Activa'])

    def test_devuelve_como_mucho_doce(self):
        for i in range(15):
            self._psi(f'Psi {i}', f'psi-{i}')
        self.assertEqual(len(self.client.get(reverse('api_destacados')).json()['profesionales']), 12)

    def test_sin_profesionales_devuelve_lista_vacia(self):
        self.assertEqual(self.client.get(reverse('api_destacados')).json(), {'profesionales': []})

    def test_se_puede_cachear_unos_minutos(self):
        self.assertIn('max-age=300', self.client.get(reverse('api_destacados'))['Cache-Control'])

    def test_los_pedidos_de_otros_sitios_no_cuentan_como_visitas(self):
        from .models import Visita
        self.client.get(reverse('api_destacados'))
        self.assertFalse(Visita.objects.filter(pagina='/api/destacados/').exists())

    def test_robots_pide_no_indexar_la_api(self):
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /api/')
