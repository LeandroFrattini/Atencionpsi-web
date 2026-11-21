from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from .models import Paciente, Turno
from .notificaciones import contexto_de_ejemplo, enviar_con_contexto, intentar_aviso_nuevo_turno


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


class AvisoFilter(admin.SimpleListFilter):
    """Qué pasó con el mail de aviso al profesional en las reservas hechas desde la web."""
    title = 'aviso al profesional'
    parameter_name = 'aviso'

    def lookups(self, request, model_admin):
        return [
            ('enviado', 'Enviado'),
            ('error', 'No salió (con error)'),
            ('sin_registro', 'Sin registro (reservas anteriores a este control)'),
        ]

    def queryset(self, request, queryset):
        web = queryset.filter(origen='publico')
        if self.value() == 'enviado':
            return web.filter(aviso_enviado_en__isnull=False)
        if self.value() == 'error':
            return web.filter(aviso_enviado_en__isnull=True).exclude(aviso_error='')
        if self.value() == 'sin_registro':
            return web.filter(aviso_enviado_en__isnull=True, aviso_error='')
        return queryset


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ('paciente', 'psicologo', 'fecha_hora', 'estado', 'origen', 'aviso_visible', 'creado_en', 'reagendado')
    list_filter = ('origen', AvisoFilter, 'estado', 'reagendado', 'psicologo')
    actions = ['reenviar_aviso_action']
    readonly_fields = ('aviso_enviado_en', 'aviso_error')

    @admin.display(description='Aviso al profesional')
    def aviso_visible(self, obj):
        if obj.origen != 'publico':
            return '—'
        if obj.aviso_enviado_en:
            hora = timezone.localtime(obj.aviso_enviado_en).strftime('%d/%m %H:%M')
            if obj.aviso_error:
                return format_html('<span title="{}" style="color:#b26a00">✔ {} (copia interna)</span>', obj.aviso_error, hora)
            return format_html('<span style="color:#2e7d32">✔ {}</span>', hora)
        if obj.aviso_error:
            return format_html('<span title="{}" style="color:#c62828;font-weight:600">✖ no salió: {}</span>', obj.aviso_error, obj.aviso_error[:60])
        return format_html('<span style="color:#888">{}</span>', 'sin registro')

    @admin.action(description='Reenviar el aviso al profesional')
    def reenviar_aviso_action(self, request, queryset):
        bien = mal = 0
        for turno in queryset.filter(origen='publico').select_related('psicologo__usuario', 'paciente'):
            if intentar_aviso_nuevo_turno(turno):
                bien += 1
            else:
                mal += 1
        if bien:
            self.message_user(request, f'Se reenvió el aviso de {bien} turno(s).', level=messages.SUCCESS)
        if mal:
            self.message_user(request, f'{mal} aviso(s) no salieron: mirá el motivo en la columna "Aviso al profesional".', level=messages.ERROR)
        if not (bien or mal):
            self.message_user(request, 'Elegí turnos reservados desde la web: son los únicos que mandan aviso.', level=messages.WARNING)

    def get_urls(self):
        return [
            path('probar-mail/', self.admin_site.admin_view(self.probar_mail_view), name='portal_turno_probar_mail'),
        ] + super().get_urls()

    @method_decorator(require_POST)
    def probar_mail_view(self, request):
        """Manda un mail de ejemplo a la copia interna con la misma configuración que los avisos de turnos y dice
        exactamente qué pasó, sin esperar a que alguien reserve."""
        if not self.has_change_permission(request):
            raise PermissionDenied
        destino = settings.TURNOS_BCC_EMAIL
        modo = 'SMTP de Brevo' if 'smtp' in settings.EMAIL_BACKEND else f'"{settings.EMAIL_BACKEND.rsplit(".", 1)[-1]}" (no manda mails de verdad)'
        estado = f'Modo: {modo}. Usuario de Brevo cargado: {"sí" if settings.EMAIL_HOST_USER else "NO"}. Clave de Brevo cargada: {"sí" if settings.EMAIL_HOST_PASSWORD else "NO"}.'
        if not destino:
            self.message_user(request, f'No hay copia interna configurada (TURNOS_BCC_EMAIL). {estado}', level=messages.ERROR)
        else:
            try:
                enviar_con_contexto(destino, contexto_de_ejemplo(), prefijo_asunto='[PRUEBA] ')
            except Exception as e:
                self.message_user(request, f'El mail de prueba NO salió: {type(e).__name__}: {e}. {estado}', level=messages.ERROR)
            else:
                self.message_user(request, f'Salió el mail de prueba a {destino}: revisá esa bandeja (y el spam). {estado}', level=messages.SUCCESS)
        return HttpResponseRedirect(reverse('admin:portal_turno_changelist') + '?origen__exact=publico&o=-6')

    search_fields = ('paciente__nombre', 'paciente__apellido', 'psicologo__nombre')
    autocomplete_fields = ('psicologo', 'paciente')
    date_hierarchy = 'fecha_hora'
