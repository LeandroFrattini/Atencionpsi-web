from django.contrib import admin
from .models import Paciente, Turno


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('apellido', 'nombre', 'psicologo', 'activo', 'creado_en')
    list_filter = ('activo', 'psicologo')
    search_fields = ('nombre', 'apellido', 'dni', 'psicologo__nombre')
    autocomplete_fields = ('psicologo',)
    fieldsets = (
        ('Datos personales', {
            'fields': ('psicologo', 'nombre', 'apellido', 'dni', 'telefono', 'email', 'fecha_nacimiento', 'activo')
        }),
        ('Historia clínica', {
            'fields': ('motivo_consulta', 'antecedentes', 'diagnostico', 'tratamiento', 'notas_generales')
        }),
    )


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'psicologo', 'fecha_hora', 'estado', 'origen', 'creado_en', 'reagendado')
    list_filter = ('origen', 'estado', 'reagendado', 'psicologo')
    search_fields = ('paciente__nombre', 'paciente__apellido', 'psicologo__nombre')
    autocomplete_fields = ('psicologo', 'paciente')
    date_hierarchy = 'fecha_hora'
