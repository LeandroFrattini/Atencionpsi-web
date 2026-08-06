from django.conf import settings
from django.db import models
from django.utils.text import slugify
import re

class Modalidad(models.Model):
    nombre = models.CharField(max_length=50)
    class Meta:
        verbose_name_plural = "Modalidades"
    def __str__(self):
        return self.nombre

class Publico(models.Model):
    nombre = models.CharField(max_length=50)
    orden = models.PositiveIntegerField(
        default=100,
        verbose_name='Orden',
        help_text='Los números más bajos aparecen primero. Empatados se ordenan alfabéticamente.'
    )
    class Meta:
        verbose_name = "Público"
        verbose_name_plural = "Públicos"
        ordering = ['orden', 'nombre']
    def __str__(self):
        return self.nombre


class Orientacion(models.Model):
    """
    Categoría fija de orientación teórica (Psicoanálisis, Cognitivo
    Conductual, etc.) para poder filtrar en el buscador. Es aparte del
    texto libre que cada profesional escribe en Psicologo.orientacion
    (que sigue existiendo tal cual, para la descripción personal en el
    perfil) -- esto es solo la etiqueta con la que se filtra.
    """
    nombre = models.CharField(max_length=80, unique=True)
    orden = models.PositiveIntegerField(
        default=100,
        verbose_name='Orden',
        help_text='Los números más bajos aparecen primero. Empatados se ordenan alfabéticamente.'
    )
    class Meta:
        verbose_name = "Orientación"
        verbose_name_plural = "Orientaciones"
        ordering = ['orden', 'nombre']
    def __str__(self):
        return self.nombre


class Ciudad(models.Model):
    nombre = models.CharField(max_length=100)
    ciudad_padre = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='barrios',
        verbose_name='Ciudad padre'
    )

    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        ordering = ['ciudad_padre__nombre', 'nombre']
        unique_together = [('nombre', 'ciudad_padre')]

    def __str__(self):
        if self.ciudad_padre:
            return f"{self.ciudad_padre.nombre} - {self.nombre}"
        return self.nombre

    def nombre_completo(self):
        return self.__str__()


class ObraSocial(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Obra Social / Prepaga"
        verbose_name_plural = "Obras Sociales / Prepagas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Psicologo(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(max_length=150, unique=True, blank=True, null=True)
    foto = models.ImageField(upload_to='psicologos/', null=True, blank=True)
    ciudad = models.CharField(max_length=100, blank=True, default='')  # campo legado
    ciudades = models.ManyToManyField('Ciudad', blank=True, verbose_name='Ciudades')
    modalidades = models.ManyToManyField(Modalidad, blank=True)
    destinatarios = models.ManyToManyField(Publico, blank=True)
    whatsapp = models.CharField(max_length=20)
    destacado = models.BooleanField(default=False)
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Si está desactivado, no aparece en el buscador público del sitio.'
    )
    orientacion = models.CharField(
        max_length=100, blank=True,
        help_text='Texto libre para el perfil (lo que escribe cada profesional). '
                   'Para que se pueda filtrar en el buscador, marcá también las Orientaciones de abajo.'
    )
    orientaciones = models.ManyToManyField(
        Orientacion, blank=True, verbose_name='Orientaciones (filtro)',
        help_text='Categorías fijas para el filtro del buscador (Psicoanálisis, Cognitivo Conductual, etc.). '
                   'Podés marcar más de una.'
    )
    descripcion = models.TextField(blank=True)
    obras_sociales = models.ManyToManyField('ObraSocial', blank=True, verbose_name='Obras Sociales / Prepagas')
    nota_facturacion = models.CharField(max_length=200, blank=True, verbose_name='Nota de facturación', help_text='Ej: Hace facturas para reintegro')
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='psicologo',
        verbose_name='Usuario de acceso al portal',
        help_text='Cuenta de login para que este profesional entre a /portal/. Se crea desde Usuarios en el admin.'
    )
    debe_cambiar_password = models.BooleanField(
        default=False,
        verbose_name='Debe cambiar la contraseña',
        help_text='Se marca sola al crear el acceso con contraseña provisoria. Se desmarca cuando el profesional la cambia.'
    )
    duracion_turno_min = models.PositiveSmallIntegerField(
        default=45,
        choices=[(30, '30 minutos'), (45, '45 minutos'), (60, '60 minutos')],
        verbose_name='Duración de los turnos',
        help_text='Se usa para partir la disponibilidad semanal en horarios reservables desde el turnero público.'
    )
    direccion_consultorio = models.CharField(
        max_length=255, blank=True,
        verbose_name='Dirección del consultorio',
        help_text='Se muestra en la reserva y en el mail de aviso cuando el turno es presencial.'
    )

    def whatsapp_limpio(self):
        """Retorna el número de WhatsApp en formato internacional sin símbolos."""
        numero = re.sub(r'[^\d]', '', self.whatsapp)
        return numero

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        # Limpiar número de WhatsApp al guardar
        self.whatsapp = re.sub(r'[^\d]', '', self.whatsapp)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


# ── ANALYTICS ──────────────────────────────────────────────

class Visita(models.Model):
    """Registra visitas por página y por día."""
    fecha = models.DateField(auto_now_add=True)
    pagina = models.CharField(max_length=200)
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('fecha', 'pagina')
        verbose_name = "Visita"
        verbose_name_plural = "Visitas"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.fecha} | {self.pagina} ({self.cantidad})"


class ClickWhatsApp(models.Model):
    """Registra clicks en el botón de WhatsApp por profesional y por día."""
    fecha = models.DateField(auto_now_add=True)
    psicologo = models.ForeignKey(Psicologo, on_delete=models.CASCADE, related_name='clicks_wa')
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('fecha', 'psicologo')
        verbose_name = "Click WhatsApp"
        verbose_name_plural = "Clicks WhatsApp"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.fecha} | {self.psicologo.nombre} ({self.cantidad})"
