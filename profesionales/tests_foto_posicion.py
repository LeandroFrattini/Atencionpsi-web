"""La foto va en un cuadrado: una foto vertical se recorta. Por defecto se prioriza la parte de arriba (donde está
la cara) y cada profesional puede tener un ajuste propio desde el admin."""
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Psicologo


def _psico(**extra):
    return Psicologo.objects.create(nombre='Lic. Prueba Foto', whatsapp='2911234567', foto='psicologos/x.jpg', activo=True, **extra)


class PosicionDeLaFotoTests(TestCase):
    def test_sin_ajuste_no_se_agrega_ningun_estilo(self):
        psico = _psico()
        for url in (reverse('buscador'), reverse('perfil_psicologo', args=[psico.slug])):
            contenido = self.client.get(url).content.decode()
            self.assertIn('psicologos/x.jpg', contenido, url)
            self.assertNotIn('--foto-y', contenido, url)

    def test_con_ajuste_la_tarjeta_y_el_perfil_lo_usan(self):
        psico = _psico(foto_posicion_vertical=3)
        for url in (reverse('buscador'), reverse('perfil_psicologo', args=[psico.slug])):
            self.assertIn('style="--foto-y: 3%"', self.client.get(url).content.decode(), url)

    def test_el_cero_tambien_cuenta_como_ajuste(self):
        """Cero es un valor válido (lo más alto de la foto), no "sin ajuste"."""
        psico = _psico(foto_posicion_vertical=0)
        self.assertIn('style="--foto-y: 0%"', self.client.get(reverse('buscador')).content.decode())

    def test_solo_acepta_de_0_a_100(self):
        psico = _psico()
        for malo in (101, 250):
            psico.foto_posicion_vertical = malo
            with self.assertRaises(ValidationError):
                psico.full_clean()
        for bueno in (None, 0, 55, 100):
            psico.foto_posicion_vertical = bueno
            psico.full_clean()

    def test_la_hoja_de_estilos_prioriza_la_parte_de_arriba_por_defecto(self):
        css = open(os.path.join(settings.BASE_DIR, 'static', 'style.css'), encoding='utf-8').read()
        for clase in ('.card-destacado-foto-clip img', '.perfil-foto-clip img'):
            bloque = css[css.index(clase):]
            bloque = bloque[:bloque.index('}')]
            self.assertIn('object-position: 50% var(--foto-y, 10%)', bloque, clase)

    def test_el_admin_permite_cargar_el_ajuste(self):
        from .admin import PsicologoAdmin
        campos = [c for _, datos in PsicologoAdmin.fieldsets for c in datos['fields']]
        self.assertIn('foto_posicion_vertical', campos)
