from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Psicologo


class PsicologoSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Psicologo.objects.exclude(slug__isnull=True).exclude(slug='')

    def location(self, obj):
        return f'/psicologo/{obj.slug}/'


class StaticSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return ['inicio', 'buscador', 'sobre_nosotros', 'faq', 'unete']

    def location(self, item):
        return reverse(item)
