from django.urls import path

from . import views

urlpatterns = [
    # Patrones literales primero -- evita cualquier ambigüedad con
    # <slug:slug>/ de más abajo (que solo matchea un curso real igual,
    # pero más claro dejarlos separados).
    path('inscripcion/<int:pk>/resultado/', views.resultado, name='cursos_resultado'),
    path('inscripcion/<int:pk>/simular-pago/', views.simular_pago, name='cursos_simular_pago'),
    path('webhook/mercadopago/', views.webhook_mercadopago, name='cursos_webhook_mercadopago'),

    path('<slug:slug>/', views.detalle_curso, name='cursos_detalle'),
    path('<slug:slug>/inscripcion/', views.inscripcion_publica, name='cursos_inscripcion_publica'),
    path('<slug:slug>/inscripcion/red-consulta/', views.inscripcion_red_consulta, name='cursos_inscripcion_red_consulta'),
]
