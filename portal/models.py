from django.db import models


class Paciente(models.Model):
    psicologo = models.ForeignKey(
        'profesionales.Psicologo', on_delete=models.CASCADE, related_name='pacientes'
    )

    # Datos básicos
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=20, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Historia clínica (por secciones)
    motivo_consulta = models.TextField(blank=True, verbose_name='Motivo de consulta')
    antecedentes = models.TextField(blank=True, verbose_name='Antecedentes')
    diagnostico = models.TextField(blank=True, verbose_name='Diagnóstico')
    tratamiento = models.TextField(blank=True, verbose_name='Tratamiento / Plan')
    notas_generales = models.TextField(blank=True, verbose_name='Notas generales')

    class Meta:
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f'{self.apellido}, {self.nombre}'


class Turno(models.Model):
    ESTADO_CHOICES = [
        ('agendado', 'Agendado'),
        ('realizado', 'Realizado'),
        ('cancelado', 'Cancelado'),
        ('ausente', 'Ausente'),
    ]

    psicologo = models.ForeignKey(
        'profesionales.Psicologo', on_delete=models.CASCADE, related_name='turnos'
    )
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='turnos')
    fecha_hora = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='agendado')
    reagendado = models.BooleanField(
        default=False, help_text='Se marca solo cuando se cambia la fecha/hora original.'
    )
    notas_sesion = models.TextField(blank=True, verbose_name='Comentarios de la sesión')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f'{self.paciente} - {self.fecha_hora:%d/%m/%Y %H:%M}'
