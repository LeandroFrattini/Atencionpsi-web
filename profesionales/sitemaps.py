from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Psicologo


class PsicologoSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        # Solo activos: los dados de baja devuelven 404 (ver detalle_psicologo),
        # y mandarle a Google URLs que 404 ensucia la cobertura del sitemap.
        return Psicologo.objects.filter(activo=True).exclude(slug__isnull=True).exclude(slug='')

    def location(self, obj):
        return f'/psicologo/{obj.slug}/'


class StaticSitemap(Sitemap):
    changefreq = 'weekly'

    PRIORIDADES = {
        'inicio': 1.0,
        'buscador': 0.9,
        'sobre_nosotros': 0.5,
        'faq': 0.6,
        'unete': 0.5,
    }

    def items(self):
        return list(self.PRIORIDADES.keys())

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.PRIORIDADES.get(item, 0.5)
