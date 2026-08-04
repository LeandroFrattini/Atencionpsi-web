from django.contrib import admin, messages
import zipfile
from io import BytesIO
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.contrib.admin import helpers
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django import forms
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect, render
from django.utils import timezone
from datetime import timedelta
from .models import Psicologo, Modalidad, Publico, Orientacion, Visita, ClickWhatsApp, Ciudad, ObraSocial


class CrearAccesoPortalForm(forms.Form):
    email = forms.EmailField(label='Email (va a ser el usuario para entrar a /portal/)')
    password_inicial = forms.CharField(
        label='Contraseña inicial',
        help_text='Por defecto es el WhatsApp cargado. El profesional va a tener que cambiarla obligatoriamente en su primer ingreso.'
    )


@admin.register(Modalidad)
class ModalidadAdmin(admin.ModelAdmin):
    list_display = ('nombre',)


@admin.register(Publico)
class PublicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'orden')
    list_editable = ('orden',)
    ordering = ('orden', 'nombre')


@admin.register(Orientacion)
class OrientacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'orden')
    list_editable = ('orden',)
    ordering = ('orden', 'nombre')


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
    list_display = ('nombre', 'ciudades_display', 'activo', 'destacado', 'clicks_totales')
    list_filter = ('activo', 'destacado', 'ciudades', 'modalidades', 'destinatarios', 'orientaciones')
    search_fields = ('nombre', 'orientacion', 'ciudades__nombre')
    prepopulated_fields = {'slug': ('nombre',)}
    filter_horizontal = ('modalidades', 'destinatarios', 'orientaciones', 'obras_sociales', 'ciudades')
    fieldsets = (
        ('Datos personales', {
            'fields': ('nombre', 'slug', 'foto', 'descripcion')
        }),
        ('Atención', {
            'fields': ('orientacion', 'orientaciones', 'ciudades', 'modalidades', 'destinatarios')
        }),
        ('Cobertura', {
            'fields': ('obras_sociales', 'nota_facturacion'),
            'description': 'Seleccioná las obras sociales que acepta y agregá una nota si trabaja con factura.'
        }),
        ('Contacto y configuración', {
            'fields': ('whatsapp', 'destacado', 'activo')
        }),
        ('Acceso al portal', {
            'fields': ('usuario',),
            'description': 'Para que este profesional pueda entrar a /portal/, primero creale un usuario en Usuarios y seleccionalo acá.'
        }),
    )
    autocomplete_fields = ('usuario',)

    def ciudades_display(self, obj):
        return ', '.join(c.nombre for c in obj.ciudades.all()) or '—'
    ciudades_display.short_description = 'Ciudades'

    def clicks_totales(self, obj):
        total = obj.clicks_wa.aggregate(t=Sum('cantidad'))['t'] or 0
        return total
    clicks_totales.short_description = 'Clicks WA'

    actions = ['generar_imagenes_action', 'crear_acceso_portal_action']

    def crear_acceso_portal_action(self, request, queryset):
        """
        Crea (o actualiza) el usuario de portal de UN psicólogo por vez:
        usuario = email, contraseña inicial = la que se indique (por defecto
        su WhatsApp). La contraseña inicial NO pasa por los validadores fuertes
        a propósito (es de un solo uso) — se marca debe_cambiar_password para
        forzar el cambio en el primer login, momento en el que sí se validan
        todas las reglas de contraseña.
        """
        if queryset.count() != 1:
            self.message_user(request, 'Elegí un solo profesional a la vez para esta acción.', level=messages.ERROR)
            return

        psicologo = queryset.first()

        if 'apply' in request.POST:
            form = CrearAccesoPortalForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email']
                password_inicial = form.cleaned_data['password_inicial']

                ya_existe = User.objects.filter(username__iexact=email)
                if psicologo.usuario_id:
                    ya_existe = ya_existe.exclude(pk=psicologo.usuario_id)

                if ya_existe.exists():
                    form.add_error('email', 'Ya hay un usuario con ese email.')
                else:
                    if psicologo.usuario:
                        user = psicologo.usuario
                        user.username = email
                        user.email = email
                    else:
                        user = User(username=email, email=email)
                    user.is_staff = False
                    user.is_superuser = False
                    user.set_password(password_inicial)
                    user.save()

                    psicologo.usuario = user
                    psicologo.debe_cambiar_password = True
                    psicologo.save(update_fields=['usuario', 'debe_cambiar_password'])

                    self.message_user(
                        request,
                        f'Acceso creado para {psicologo.nombre}. Usuario: {email} — '
                        f'contraseña inicial: {password_inicial}. Pasale estos datos; '
                        f'en el primer ingreso va a tener que cambiarla.',
                        level=messages.SUCCESS,
                    )
                    return redirect(request.path)
        else:
            form = CrearAccesoPortalForm(initial={'password_inicial': psicologo.whatsapp_limpio()})

        context = {
            **self.admin_site.each_context(request),
            'title': f'Crear acceso al portal para {psicologo.nombre}',
            'psicologo': psicologo,
            'form': form,
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(request, 'admin/crear_acceso_portal.html', context)

    crear_acceso_portal_action.short_description = 'Crear acceso al portal (email + contraseña inicial)'

    def generar_imagenes_action(self, request, queryset):
        """Acción de admin: genera la historia de Instagram (1080x1920) de cada psicólogo seleccionado."""
        from .generador_imagenes import generar_imagen_story

        if 'apply' in request.POST:
            telefono_manual = request.POST.get('telefono_manual', '').strip()
            buf = BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for p in queryset:
                    nombre_slug = p.slug or p.nombre.lower().replace(' ', '-')
                    story_img = generar_imagen_story(p, telefono_manual=telefono_manual or None)
                    story_buf = BytesIO()
                    story_img.save(story_buf, 'JPEG', quality=92)
                    zf.writestr(f'{nombre_slug}_historia.jpg', story_buf.getvalue())

            buf.seek(0)
            response = HttpResponse(buf.read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="historias_psicologos.zip"'
            return response

        context = {
            **self.admin_site.each_context(request),
            'title': 'Generar historias de Instagram',
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'media': self.media,
        }
        return TemplateResponse(request, 'admin/generar_imagenes.html', context)

    generar_imagenes_action.short_description = 'Generar historia de Instagram'



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
