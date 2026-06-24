from django.contrib import admin
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django import forms
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from .models import Psicologo, Modalidad, Publico, Visita, ClickWhatsApp, Ciudad


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
    list_display = ('nombre', 'ciudad_obj', 'destacado', 'clicks_totales')
    list_filter = ('destacado', 'ciudad_obj', 'modalidades', 'destinatarios')
    search_fields = ('nombre', 'orientacion', 'ciudad_obj__nombre')
    prepopulated_fields = {'slug': ('nombre',)}
    filter_horizontal = ('modalidades', 'destinatarios')

    def clicks_totales(self, obj):
        total = obj.clicks_wa.aggregate(t=Sum('cantidad'))['t'] or 0
        return total
    clicks_totales.short_description = 'Clicks WA'



@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

# ── ANALYTICS ──────────────────────────────────────────────

@admin.register(Visita)
class VisitaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'pagina', 'cantidad')
    list_filter = ('fecha',)
    ordering = ('-fecha', '-cantidad')
    readonly_fields = ('fecha', 'pagina', 'cantidad')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ClickWhatsApp)
class ClickWhatsAppAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'psicologo_nombre', 'cantidad')
    list_filter = ('fecha',)
    ordering = ('-fecha', '-cantidad')
    readonly_fields = ('fecha', 'psicologo', 'cantidad')

    def psicologo_nombre(self, obj):
        return obj.psicologo.nombre
    psicologo_nombre.short_description = 'Profesional'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ── PANEL DE ANALYTICS PERSONALIZADO ──────────────────────

class AnalyticsAdmin(admin.ModelAdmin):
    """Panel de resumen de estadísticas."""

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('resumen/', self.admin_site.admin_view(self.resumen_view), name='analytics_resumen'),
        ]
        return custom + urls

    def resumen_view(self, request):
        hoy = timezone.localdate()
        hace_30 = hoy - timedelta(days=30)

        # Visitas últimos 30 días por día
        visitas_diarias = (
            Visita.objects
            .filter(fecha__gte=hace_30)
            .values('fecha')
            .annotate(total=Sum('cantidad'))
            .order_by('-fecha')
        )

        # Total visitas mes actual
        total_visitas_mes = (
            Visita.objects
            .filter(fecha__year=hoy.year, fecha__month=hoy.month)
            .aggregate(t=Sum('cantidad'))['t'] or 0
        )

        # Total clicks WA mes actual
        total_wa_mes = (
            ClickWhatsApp.objects
            .filter(fecha__year=hoy.year, fecha__month=hoy.month)
            .aggregate(t=Sum('cantidad'))['t'] or 0
        )

        # Top profesionales por clicks (todo el tiempo)
        top_profesionales = (
            ClickWhatsApp.objects
            .values('psicologo__nombre')
            .annotate(total=Sum('cantidad'))
            .order_by('-total')[:15]
        )

        # Clicks WA últimos 30 días por día
        wa_diarios = (
            ClickWhatsApp.objects
            .filter(fecha__gte=hace_30)
            .values('fecha')
            .annotate(total=Sum('cantidad'))
            .order_by('-fecha')
        )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Resumen de Analytics',
            'visitas_diarias': visitas_diarias,
            'total_visitas_mes': total_visitas_mes,
            'total_wa_mes': total_wa_mes,
            'top_profesionales': top_profesionales,
            'wa_diarios': wa_diarios,
            'mes_actual': hoy.strftime('%B %Y'),
        }
        return render(request, 'admin/analytics_resumen.html', context)
