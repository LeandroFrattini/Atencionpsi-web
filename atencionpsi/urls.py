from django.contrib import admin
from django.urls import path, re_path
from profesionales import views
from django.conf import settings
from django.views.static import serve # Esto es lo que va a rescatar tus estilos

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.inicio, name='inicio'),
    path('buscador/', views.buscador, name='buscador'),
    path('psicologo/<slug:slug>/', views.detalle_psicologo, name='perfil_psicologo'),
    path('unete-al-equipo/', views.unete, name='unete'),
    path('sobre_nosotros/', views.sobre_nosotros, name='sobre_nosotros'),
    path('preguntas-frecuentes/', views.faq, name='faq'),
]

# ESTA ES LA CLAVE: Forzamos a Django a servir estáticos y media 
# ignorando si el DEBUG es True o False.
urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]