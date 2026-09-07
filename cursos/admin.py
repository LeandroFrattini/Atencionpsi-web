from django.contrib import admin

from .models import Curso, InscripcionCurso


class InscripcionInline(admin.TabularInline):
    model = InscripcionCurso
    extra = 0
    fields = ('nombre', 'email', 'whatsapp', 'es_red_consulta', 'monto', 'estado', 'fecha_creacion')
    readonly_fields = ('nombre', 'email', 'whatsapp', 'es_red_consulta', 'monto', 'fecha_creacion')
    can_delete = False


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha', 'hora', 'presentador', 'precio_red_consulta', 'precio_publico', 'inscripciones_aprobadas', 'cupo_maximo', 'activo')
    list_filter = ('activo',)
    prepopulated_fields = {'slug': ('nombre',)}
    inlines = [InscripcionInline]

    @admin.display(description='Pagadas')
    def inscripciones_aprobadas(self, obj):
        return obj.inscripciones_aprobadas


@admin.register(InscripcionCurso)
class InscripcionCursoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'curso', 'email', 'whatsapp', 'es_red_consulta', 'monto', 'estado', 'fecha_creacion')
    list_filter = ('curso', 'estado', 'es_red_consulta')
    search_fields = ('nombre', 'email', 'whatsapp')
    readonly_fields = ('mp_preference_id', 'mp_payment_id', 'fecha_creacion', 'fecha_aprobado')
