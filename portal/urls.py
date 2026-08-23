from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('login/', LoginView.as_view(template_name='portal/login.html'), name='portal_login'),
    path('logout/', LogoutView.as_view(), name='portal_logout'),

    path('', views.dashboard, name='portal_dashboard'),
    path('cambiar-password/', views.cambiar_password, name='portal_cambiar_password'),

    path('admin/', views.admin_dashboard, name='portal_admin_dashboard'),
    path('admin/agenda/', views.admin_agenda, name='portal_admin_agenda'),
    path('admin/finanzas/', views.admin_finanzas, name='portal_admin_finanzas'),
    path('admin/psicologo/<int:pk>/dar-de-alta-baja/', views.psicologo_toggle_activo, name='portal_psicologo_toggle'),
    path('admin/psicologo/<int:pk>/destacar/', views.psicologo_toggle_destacado, name='portal_psicologo_toggle_destacado'),
    path('admin/psicologo/<int:pk>/crear-acceso/', views.psicologo_crear_acceso, name='portal_psicologo_crear_acceso'),
    path('admin/psicologo/<int:pk>/blanquear-password/', views.psicologo_blanquear_password, name='portal_psicologo_blanquear_password'),

    path('admin/pago/nuevo/', views.pago_nuevo, name='portal_pago_nuevo'),
    path('admin/pago/<int:pk>/eliminar/', views.pago_eliminar, name='portal_pago_eliminar'),
    path('admin/pago/<int:pk>/asignar/', views.pago_asignar, name='portal_pago_asignar'),
    path('admin/pago/sincronizar-mercadopago/', views.pago_sincronizar_mercadopago, name='portal_pago_sincronizar_mercadopago'),
    path('admin/gasto/nuevo/', views.gasto_nuevo, name='portal_gasto_nuevo'),
    path('admin/gasto/<int:pk>/eliminar/', views.gasto_eliminar, name='portal_gasto_eliminar'),

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

    path('disponibilidad/', views.disponibilidad, name='portal_disponibilidad'),
    path('disponibilidad/bloque/nuevo/', views.disponibilidad_bloque_crear, name='portal_disponibilidad_bloque_crear'),
    path('disponibilidad/bloque/<int:pk>/eliminar/', views.disponibilidad_bloque_eliminar, name='portal_disponibilidad_bloque_eliminar'),
    path('disponibilidad/no-atiende/nuevo/', views.excepcion_crear, name='portal_excepcion_crear'),
    path('disponibilidad/no-atiende/<int:pk>/eliminar/', views.excepcion_eliminar, name='portal_excepcion_eliminar'),
]
