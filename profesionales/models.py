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


def _foto_con_orientacion_correcta(foto_field):
    """
    Si la foto tiene tag EXIF de orientación (típico en fotos sacadas con
    el celular en vertical), devuelve una versión nueva con los píxeles ya
    rotados en el sentido correcto y ese tag eliminado -- así se ve bien en
    cualquier visor, respete o no el EXIF. Si no tiene nada que corregir,
    devuelve la foto tal cual (no se re-comprime sin necesidad).
    """
    from io import BytesIO
    from PIL import Image, ImageOps
    from django.core.files.base import ContentFile

    foto_field.file.seek(0)
    try:
        imagen = Image.open(foto_field.file)
        imagen.load()
        orientacion = imagen.getexif().get(0x0112)  # tag EXIF de orientación
    except Exception:
        # Archivo corrupto o no reconocible como imagen -- lo dejamos pasar
        # tal cual; que falle (o no) más adelante donde ya fallaba antes.
        return foto_field
    finally:
        foto_field.file.seek(0)

    if not orientacion or orientacion == 1:
        return foto_field

    formato = imagen.format or 'JPEG'
    imagen = ImageOps.exif_transpose(imagen)
    guardar_kwargs = {'format': formato}
    if formato == 'JPEG':
        if imagen.mode not in ('RGB', 'L'):
            imagen = imagen.convert('RGB')
        guardar_kwargs['quality'] = 90

    buffer = BytesIO()
    imagen.save(buffer, **guardar_kwargs)
    buffer.seek(0)
    return ContentFile(buffer.read(), name=foto_field.name)


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

    # --- Datos comerciales: privados, solo se ven en este admin de Django.
    # No se muestran en el portal del profesional ni en ningún lado del sitio público. ---
    PLAN_CHOICES = [
        ('avanzado', 'Avanzado'),
        ('premium', 'Premium'),
        ('master', 'Master'),
    ]
    TIPO_PAGO_CHOICES = [
        ('transferencia', 'Transferencia'),
        ('suscripcion', 'Suscripción'),
    ]
    fecha_alta = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha de alta',
    )
    plan = models.CharField(
        max_length=20, choices=PLAN_CHOICES, blank=True,
        verbose_name='Plan',
    )
    monto_pagado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Monto pagado',
    )
    tipo_pago = models.CharField(
        max_length=20, choices=TIPO_PAGO_CHOICES, blank=True,
        verbose_name='Transferencia o suscripción',
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
        # Fotos sacadas con el celular en vertical suelen guardar los
        # píxeles "acostados" y un tag EXIF que le dice al que la mira
        # "rotala". La mayoría de los navegadores lo respetan, pero no
        # todos (ni WhatsApp/redes al generar la vista previa) -- por eso
        # se ve derecha en algunos lados y de costado en otros. Achatamos
        # la rotación en los píxeles mismos al subir la foto, así se ve
        # bien en cualquier lado sin depender de quién la mire.
        if self.foto and not self.foto._committed:
            self.foto = _foto_con_orientacion_correcta(self.foto)
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
