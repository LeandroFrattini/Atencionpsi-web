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
from django.utils import timezone, dateformat
from datetime import timedelta
from .models import Psicologo, Modalidad, Publico, Orientacion, Visita, ClickWhatsApp, Ciudad, ObraSocial
from portal.models import Pago


class CrearAccesoPortalForm(forms.Form):
    email = forms.EmailField(label='Email (va a ser el usuario para entrar a /portal/)')
    password_inicial = forms.CharField(
        label='Contraseña inicial',
        help_text='Por defecto es el WhatsApp cargado. El profesional va a tener que cambiarla obligatoriamente en su primer ingreso.'
    )

    def clean_email(self):
        # Siempre en minúscula: si se guarda mezclado (p.ej. "Juan@Gmail.com")
        # y el profesional lo escribe distinto al loguearse, el login falla
        # aunque la contraseña esté bien.
        return self.cleaned_data['email'].strip().lower()


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


def _concepto_mensualidad(fecha):
    """'Mensualidad <mes> <año>', ej 'Mensualidad septiembre 2026' -- con
    dateformat de Django (no strftime) para que el nombre del mes salga
    siempre en español sin depender del locale del sistema operativo."""
    return f'Mensualidad {dateformat.format(fecha, "F Y")}'


class PagoMesActualFilter(admin.SimpleListFilter):
    """Filtro para elegir de un tiro a todos los que ya pagaron o a todos
    los que todavía no pagaron este mes -- así se puede tildar 'No' y
    seleccionar todos con el checkbox de 'elegir todos' antes de usar la
    acción de marcar el pago, en vez de ir tildando uno por uno."""
    title = 'pagó este mes'
    parameter_name = 'pago_mes'

    def lookups(self, request, model_admin):
        return (('si', 'Sí'), ('no', 'No'))

    def queryset(self, request, queryset):
        if self.value() not in ('si', 'no'):
            return queryset
        hoy = timezone.localdate()
        ids_pagados = Pago.objects.filter(
            fecha__year=hoy.year, fecha__month=hoy.month,
            concepto__istartswith='Mensualidad',
        ).values_list('psicologo_id', flat=True)
        if self.value() == 'si':
            return queryset.filter(pk__in=ids_pagados)
        return queryset.exclude(pk__in=ids_pagados)


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
    list_display = (
        'nombre', 'plan', 'fecha_alta', 'tipo_pago',
        'pago_mes_actual', 'activo', 'clicks_totales',
    )
    list_filter = (
        'plan', 'tipo_pago', PagoMesActualFilter, 'activo', 'destacado',
        'ciudades', 'modalidades', 'destinatarios', 'orientaciones',
    )
    search_fields = ('nombre', 'orientacion', 'ciudades__nombre')
    prepopulated_fields = {'slug': ('nombre',)}
    filter_horizontal = ('modalidades', 'destinatarios', 'orientaciones', 'obras_sociales', 'ciudades')
    fieldsets = (
        ('Datos personales', {
            'fields': ('nombre', 'slug', 'foto', 'descripcion')
        }),
        ('Datos comerciales (privado -- solo vos lo ves acá)', {
            'fields': ('fecha_alta', 'plan', 'monto_pagado', 'tipo_pago'),
            'description': 'Información interna de facturación. No se muestra en el portal del profesional ni en ningún lado del sitio público.'
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

    def clicks_totales(self, obj):
        total = obj.clicks_wa.aggregate(t=Sum('cantidad'))['t'] or 0
        return total
    clicks_totales.short_description = 'Clicks WA'

    def pago_mes_actual(self, obj):
        hoy = timezone.localdate()
        pagado = Pago.objects.filter(
            psicologo=obj, fecha__year=hoy.year, fecha__month=hoy.month,
            concepto__istartswith='Mensualidad',
        ).exists()
        return '✅' if pagado else '—'
    pago_mes_actual.short_description = 'Pagó este mes'

    actions = [
        'generar_imagenes_action', 'generar_imagen_feed_action',
        'crear_acceso_portal_action', 'marcar_pago_mes_action',
    ]

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

    def generar_imagen_feed_action(self, request, queryset):
        """Acción de admin: genera el post de feed (1080x1350) de cada psicólogo seleccionado."""
        from .generador_imagenes import generar_imagen_feed

        if 'apply' in request.POST:
            buf = BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for p in queryset:
                    nombre_slug = p.slug or p.nombre.lower().replace(' ', '-')
                    feed_img = generar_imagen_feed(p)
                    feed_buf = BytesIO()
                    feed_img.save(feed_buf, 'JPEG', quality=92)
                    zf.writestr(f'{nombre_slug}_feed.jpg', feed_buf.getvalue())

            buf.seek(0)
            response = HttpResponse(buf.read(), content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="posts_feed_psicologos.zip"'
            return response

        context = {
            **self.admin_site.each_context(request),
            'title': 'Generar posts de feed de Instagram',
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'media': self.media,
        }
        return TemplateResponse(request, 'admin/generar_imagen_feed.html', context)

    generar_imagen_feed_action.short_description = 'Generar post de feed de Instagram'

    def marcar_pago_mes_action(self, request, queryset):
        """
        Registra en Finanzas el ingreso de la mensualidad de este mes para
        cada profesional seleccionado, usando el monto que tiene cargado en
        "Monto pagado". No duplica: si un profesional ya tiene un pago de
        "Mensualidad <mes>" cargado este mes (a mano o por esta misma
        acción), se lo salta. Si no tiene monto cargado, también se lo
        salta -- no hay nada que registrar.
        """
        hoy = timezone.localdate()
        mes_nombre = dateformat.format(hoy, 'F Y')
        concepto = _concepto_mensualidad(hoy)

        def _separar(queryset):
            a_marcar, ya_pagados, sin_monto = [], [], []
            for p in queryset:
                ya_existe = Pago.objects.filter(
                    psicologo=p, fecha__year=hoy.year, fecha__month=hoy.month,
                    concepto__istartswith='Mensualidad',
                ).exists()
                if ya_existe:
                    ya_pagados.append(p)
                elif not p.monto_pagado:
                    sin_monto.append(p)
                else:
                    a_marcar.append(p)
            return a_marcar, ya_pagados, sin_monto

        if 'apply' in request.POST:
            a_marcar, ya_pagados, sin_monto = _separar(queryset)
            for p in a_marcar:
                Pago.objects.create(psicologo=p, fecha=hoy, monto=p.monto_pagado, concepto=concepto)

            if a_marcar:
                self.message_user(
                    request,
                    f'Pago de "{concepto}" registrado en Finanzas para: '
                    f'{", ".join(p.nombre for p in a_marcar)}.',
                    level=messages.SUCCESS,
                )
            if ya_pagados:
                self.message_user(
                    request,
                    f'Ya tenían un pago de este mes cargado, no se duplicó: '
                    f'{", ".join(p.nombre for p in ya_pagados)}.',
                    level=messages.WARNING,
                )
            if sin_monto:
                self.message_user(
                    request,
                    f'No tienen "Monto pagado" cargado en su ficha, no se les pudo '
                    f'registrar el pago: {", ".join(p.nombre for p in sin_monto)}.',
                    level=messages.ERROR,
                )
            return redirect(request.path)

        a_marcar, ya_pagados, sin_monto = _separar(queryset)
        context = {
            **self.admin_site.each_context(request),
            'title': f'Marcar pago de {mes_nombre}',
            'mes_nombre': mes_nombre,
            'a_marcar': a_marcar,
            'ya_pagados': ya_pagados,
            'sin_monto': sin_monto,
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(request, 'admin/marcar_pago_mes.html', context)

    marcar_pago_mes_action.short_description = 'Marcar pago de este mes'


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
