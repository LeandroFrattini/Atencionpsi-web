from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('login/', LoginView.as_view(template_name='portal/login.html'), name='portal_login'),
    path('logout/', LogoutView.as_view(), name='portal_logout'),

    path('', views.dashboard, name='portal_dashboard'),
    path('cambiar-password/', views.cambiar_password, name='portal_cambiar_password'),

    path('admin/', views.admin_dashboard, name='portal_admin_dashboard'),
    path('admin/psicologo/<int:pk>/dar-de-alta-baja/', views.psicologo_toggle_activo, name='portal_psicologo_toggle'),

    path('pacientes/', views.pacientes_lista, name='portal_pacientes'),
    path('pacientes/nuevo/', views.paciente_nuevo, name='portal_paciente_nuevo'),
    path('pacientes/<int:pk>/', views.paciente_detalle, name='portal_paciente_detalle'),
    path('pacientes/<int:pk>/editar/', views.paciente_editar, name='portal_paciente_editar'),

    path('turnos/nuevo/', views.turno_nuevo, name='portal_turno_nuevo'),
    path('turnos/<int:pk>/editar/', views.turno_editar, name='portal_turno_editar'),
    path('turnos/<int:pk>/marcar-realizado/', views.turno_marcar_realizado, name='portal_turno_marcar_realizado'),
    path('turnos/<int:pk>/marcar-pagado/', views.turno_marcar_pagado, name='portal_turno_marcar_pagado'),
    path('turnos/<int:pk>/reagendar-rapido/', views.turno_reagendar_rapido, name='portal_turno_reagendar_rapido'),
    path('turnos/<int:pk>/mover/', views.turno_mover, name='portal_turno_mover'),
]
