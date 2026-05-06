from django.contrib import admin
from django import forms
from .models import Psicologo, Modalidad, Publico

@admin.register(Modalidad)
class ModalidadAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

@admin.register(Publico)
class PublicoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

class PsicologoAdminForm(forms.ModelForm):
    class Meta:
        model = Psicologo
        fields = '__all__'
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4, 'cols': 40}),
            'obras_sociales': forms.Textarea(attrs={'rows': 3, 'cols': 40}),
        }

@admin.register(Psicologo)
class PsicologoAdmin(admin.ModelAdmin):
    form = PsicologoAdminForm
    list_display = ('nombre', 'ciudad', 'destacado')
    list_filter = ('destacado', 'modalidades', 'destinatarios')
    search_fields = ('nombre', 'orientacion')
    prepopulated_fields = {'slug': ('nombre',)}
    # Interfaz de dos columnas para elegir múltiples opciones
    filter_horizontal = ('modalidades', 'destinatarios')