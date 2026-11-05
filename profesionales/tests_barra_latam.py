"""Link a atencionpsi.lat para quien busca psicólogos en otros países."""
from django.test import TestCase
from django.urls import reverse

DESTINO = 'https://atencionpsi.lat/?utm_source=atencionpsi.com.ar'


class BarraOtrosPaisesTests(TestCase):
    def test_todas_las_paginas_publicas_traen_la_barra_y_el_link_del_pie(self):
        for nombre in ('inicio', 'buscador', 'sobre_nosotros', 'faq', 'unete'):
            contenido = self.client.get(reverse(nombre)).content.decode()
            self.assertIn('barra-latam', contenido, nombre)
            self.assertIn(f'{DESTINO}&amp;utm_medium=barra_superior'.replace('&amp;', '&'), contenido, nombre)
            self.assertIn('utm_medium=footer', contenido, nombre)
            self.assertIn('Perú, Uruguay, Chile y México', contenido, nombre)

    def test_el_link_lleva_a_la_pagina_principal_de_latam(self):
        contenido = self.client.get(reverse('inicio')).content.decode()
        self.assertIn('href="https://atencionpsi.lat/?utm_source=atencionpsi.com.ar&utm_medium=barra_superior"', contenido)
