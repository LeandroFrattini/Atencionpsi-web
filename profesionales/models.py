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
    class Meta:
        verbose_name = "Público"
        verbose_name_plural = "Públicos"
    def __str__(self):
        return self.nombre


class Ciudad(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


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
    ciudad_obj = models.ForeignKey('Ciudad', null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Ciudad')
    modalidades = models.ManyToManyField(Modalidad, blank=True)
    destinatarios = models.ManyToManyField(Publico, blank=True)
    whatsapp = models.CharField(max_length=20)
    destacado = models.BooleanField(default=False)
    orientacion = models.CharField(max_length=100, blank=True)
    descripcion = models.TextField(blank=True)
    obras_sociales = models.ManyToManyField('ObraSocial', blank=True, verbose_name='Obras Sociales / Prepagas')
    nota_facturacion = models.CharField(max_length=200, blank=True, verbose_name='Nota de facturación', help_text='Ej: Hace facturas para reintegro')

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
