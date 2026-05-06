from django.db import models
from django.utils.text import slugify

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

class Psicologo(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(max_length=150, unique=True, blank=True, null=True)
    foto = models.ImageField(upload_to='psicologos/', null=True, blank=True)
    ciudad = models.CharField(max_length=100, blank=True, default='')
    
    # Ambos campos ahora son de selección múltiple
    modalidades = models.ManyToManyField(Modalidad, blank=True)
    destinatarios = models.ManyToManyField(Publico, blank=True)
    
    whatsapp = models.CharField(max_length=20) 
    destacado = models.BooleanField(default=False)
    orientacion = models.CharField(max_length=100, blank=True)
    descripcion = models.TextField(blank=True)
    obras_sociales = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre