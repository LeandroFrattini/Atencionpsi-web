from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('login/', LoginView.as_view(template_name='portal/login.html'), name='portal_login'),
    path('logout/', LogoutView.as_view(), name='portal_logout'),

    path('', views.dashboard, name='portal_dashboard'),
    path('cambiar-password/', views.cambiar_password, name='portal_cambiar_password'),

    path('pacientes/', views.pacientes_lista, name='portal_pacientes'),
    path('pacientes/nuevo/', views.paciente_nuevo, name='portal_paciente_nuevo'),
    path('pacientes/<int:pk>/', views.paciente_detalle, name='portal_paciente_detalle'),
    path('pacientes/<int:pk>/editar/', views.paciente_editar, name='portal_paciente_editar'),

    path('turnos/nuevo/', views.turno_nuevo, name='portal_turno_nuevo'),
    path('turnos/<int:pk>/editar/', views.turno_editar, name='portal_turno_editar'),
]
