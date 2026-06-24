from django.contrib import admin
from django.urls import path, re_path
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from django.conf import settings
from django.views.static import serve
from profesionales import views
from profesionales.sitemaps import PsicologoSitemap, StaticSitemap

sitemaps = {
    'psicologos': PsicologoSitemap,
    'static': StaticSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),

    # Páginas principales
    path('', views.inicio, name='inicio'),
    path('buscador/', views.buscador, name='buscador'),
    path('psicologo/<slug:slug>/', views.detalle_psicologo, name='perfil_psicologo'),
    path('unete-al-equipo/', views.unete, name='unete'),
    path('sobre-nosotros/', views.sobre_nosotros, name='sobre_nosotros'),  # guion, no underscore
    path('preguntas-frecuentes/', views.faq, name='faq'),

    # Redirect WhatsApp (registra el click)
    path('wa/<slug:slug>/', views.wa_redirect, name='wa_redirect'),

    # SEO
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
]

# Servir estáticos y media en producción
urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
