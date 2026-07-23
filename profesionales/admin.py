from django.contrib import admin
import zipfile
from io import BytesIO
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.contrib.admin import helpers
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django import forms
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from .models import Psicologo, Modalidad, Publico, Visita, ClickWhatsApp, Ciudad, ObraSocial


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
        }


@admin.register(Psicologo)
class PsicologoAdmin(admin.ModelAdmin):
    form = PsicologoAdminForm
    list_display = ('nombre', 'ciudades_display', 'destacado', 'clicks_totales')
    list_filter = ('destacado', 'ciudades', 'modalidades', 'destinatarios')
    search_fields = ('nombre', 'orientacion', 'ciudades__nombre')
    prepopulated_fields = {'slug': ('nombre',)}
    filter_horizontal = ('modalidades', 'destinatarios', 'obras_sociales', 'ciudades')
    fieldsets = (
        ('Datos personales', {
            'fields': ('nombre', 'slug', 'foto', 'descripcion')
        }),
        ('Atención', {
            'fields': ('orientacion', 'ciudades', 'modalidades', 'destinatarios')
        }),
        ('Cobertura', {
            'fields': ('obras_sociales', 'nota_facturacion'),
            'description': 'Seleccioná las obras sociales que acepta y agregá una nota si trabaja con factura.'
        }),
        ('Contacto y configuración', {
            'fields': ('whatsapp', 'destacado')
        }),
    )

    def ciudades_display(self, obj):
        return ', '.join(c.nombre for c in obj.ciudades.all()) or '—'
    ciudades_display.short_description = 'Ciudades'

    def clicks_totales(self, obj):
        total = obj.clicks_wa.aggregate(t=Sum('cantidad'))['t'] or 0
        return total
    clicks_totales.short_description = 'Clicks WA'

    actions = ['generar_imagenes_action']

    def generar_imagenes_action(self, request, queryset):
        """Acción de admin: genera post + story para los psicólogos seleccionados."""
        from .generador_imagenes import generar_imagen_post, generar_imagen_story

        if 'apply' in request.POST:
            color_top = request.POST.get('color_top', 'verde')
            color_bot = request.POST.get('color_bottom', 'rosa')

            buf = BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for p in queryset:
                    nombre_slug = p.slug or p.nombre.lower().replace(' ', '-')

                    # Post 1080×1080
                    post_img = generar_imagen_post(p, color_top, color_bot)
                    post_buf = BytesIO()
                    post_img.save(post_buf, 'JPEG', quality=92)
                    zf.writestr(f'{nombre_slug}_post.jpg', post_buf.getvalue())

                    # Story 1080×1920
                    story_img = generar_imagen_story(p)
                    story_buf = BytesIO()
                    story_img.save(story_buf, 'JPEG', quality=92)
                    zf.writestr(f'{nombre_slug}_story.jpg', story_buf.getvalue())

            buf.seek(0)
            response = HttpResponse(buf.read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="imagenes_psicologos.zip"'
            return response

        # Mostrar formulario de selección de color
        context = {
            **self.admin_site.each_context(request),
            'title': 'Generar imágenes para redes sociales',
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'media': self.media,
        }
        return TemplateResponse(request, 'admin/generar_imagenes.html', context)

    generar_imagenes_action.short_description = 'Generar imágenes para redes sociales'



@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ('nombre_display', 'ciudad_padre', 'cantidad_barrios')
    list_filter = ('ciudad_padre',)
    search_fields = ('nombre',)
    ordering = ('ciudad_padre__nombre', 'nombre')

    def nombre_display(self, obj):
        return str(obj)
    nombre_display.short_description = 'Nombre'

    def cantidad_barrios(self, obj):
        count = obj.barrios.count()
        return count if count else '-'
    cantidad_barrios.short_description = 'Barrios/Zonas'


@admin.register(ObraSocial)
class ObraSocialAdmin(admin.ModelAdmin):
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
