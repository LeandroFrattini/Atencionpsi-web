from django.contrib import admin
from django.urls import path
from profesionales import views  # Importamos las vistas de tu app
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.inicio, name='inicio'),
    path('buscador/', views.buscador, name='buscador'),
    path('psicologo/<slug:slug>/', views.detalle_psicologo, name='perfil_psicologo'),
    path('unete-al-equipo/', views.unete, name='unete'),
    path('psicologo/<slug:slug>/', views.detalle_psicologo, name='perfil_psicologo'),
]


# Esto permite que las fotos se vean durante el desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)