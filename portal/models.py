from django.db import models
from django.utils import timezone


class Pago(models.Model):
    """
    Pago recibido de un profesional (alta o mensualidad). Puede cargarse a
    mano (como siempre) o traerse solo desde Mercado Pago -- ver
    profesionales/mercadopago.py y el comando sincronizar_pagos_mercadopago.
    Privado: solo se ve en el Panel general, nunca en el portal de los
    profesionales ni en el sitio público.
    """
    ORIGEN_CHOICES = [
        ('manual', 'Cargado a mano'),
        ('transferencia', 'Transferencia (Mercado Pago)'),
        ('suscripcion', 'Suscripción (Mercado Pago)'),
    ]

    psicologo = models.ForeignKey(
        'profesionales.Psicologo', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pagos_recibidos',
    )
    fecha = models.DateField(default=timezone.localdate, verbose_name='Fecha')
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto neto recibido')
    concepto = models.CharField(
        max_length=200, blank=True, verbose_name='Concepto',
        help_text='Ej: Alta, mensualidad agosto',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    # Campos que solo se completan cuando el pago vino de la sincronización
    # con Mercado Pago -- en un pago cargado a mano quedan vacíos.
    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default='manual')
    mp_payment_id = models.CharField(
        'ID de pago en Mercado Pago', max_length=40, blank=True, unique=True, null=True,
        help_text='Evita importar el mismo pago dos veces',
    )
    monto_bruto = models.DecimalField(
        'Monto bruto (antes de la comisión de MP)', max_digits=10, decimal_places=2,
        null=True, blank=True,
    )
    pagador_nombre = models.CharField(
        'Nombre del pagador en Mercado Pago', max_length=150, blank=True,
        help_text='Tal cual lo reporta MP -- útil para asignar el pago a mano si no coincide con nadie cargado',
    )

    class Meta:
        verbose_name = 'Pago recibido'
        verbose_name_plural = 'Pagos recibidos'
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        quien = self.psicologo.nombre if self.psicologo else (self.pagador_nombre or 'Sin asignar')
        return f'{self.fecha} · {quien} · ${self.monto}'


class Gasto(models.Model):
    """Egreso del negocio -- carga manual de la dueña del sitio. Privado."""
    fecha = models.DateField(default=timezone.localdate, verbose_name='Fecha')
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto')
    concepto = models.CharField(max_length=200, blank=True, verbose_name='Concepto')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Gasto'
        verbose_name_plural = 'Gastos'
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return f'{self.fecha} · ${self.monto} · {self.concepto}'


class IngresoPortal(models.Model):
    """
    Registra que un profesional entró al portal, por día -- para ver si la
    agenda se está usando o no, sin guardar nada más que eso (mismo criterio
    que ClickWhatsApp en profesionales: una fila por psicólogo y día).
    """
    fecha = models.DateField(auto_now_add=True)
    psicologo = models.ForeignKey(
        'profesionales.Psicologo', on_delete=models.CASCADE, related_name='ingresos_portal'
    )
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('fecha', 'psicologo')
        verbose_name = 'Ingreso al portal'
        verbose_name_plural = 'Ingresos al portal'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.fecha} | {self.psicologo.nombre} ({self.cantidad})'


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
    MODALIDAD_CHOICES = [
        ('presencial', 'Presencial'),
        ('virtual', 'Virtual'),
    ]
    ORIGEN_CHOICES = [
        ('manual', 'Cargado por el profesional'),
        ('publico', 'Reservado por el paciente'),
    ]

    psicologo = models.ForeignKey(
        'profesionales.Psicologo', on_delete=models.CASCADE, related_name='turnos'
    )
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='turnos')
    fecha_hora = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='agendado')
    modalidad = models.CharField(max_length=20, choices=MODALIDAD_CHOICES, default='presencial')
    origen = models.CharField(
        max_length=20, choices=ORIGEN_CHOICES, default='manual',
        help_text='"Reservado por el paciente" es lo que dispara el mail de aviso al profesional.'
    )
    pagado = models.BooleanField(default=False, verbose_name='Pagado')
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


class DisponibilidadSemanal(models.Model):
    """
    Plantilla de disponibilidad de un psicólogo, por día de la semana --
    se define una sola vez y se repite sola todas las semanas (no hay que
    volver a cargarla). El turnero público parte cada bloque en turnos de
    `Psicologo.duracion_turno_min` para ofrecerlos como horarios reservables.
    """
    DIA_CHOICES = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
        (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'),
    ]
    MODALIDAD_CHOICES = Turno.MODALIDAD_CHOICES

    psicologo = models.ForeignKey(
        'profesionales.Psicologo', on_delete=models.CASCADE, related_name='disponibilidad_semanal'
    )
    dia_semana = models.PositiveSmallIntegerField(choices=DIA_CHOICES, verbose_name='Día de la semana')
    hora_desde = models.TimeField(verbose_name='Desde')
    hora_hasta = models.TimeField(verbose_name='Hasta')
    modalidad = models.CharField(max_length=20, choices=MODALIDAD_CHOICES)

    class Meta:
        verbose_name = 'Bloque de disponibilidad semanal'
        verbose_name_plural = 'Disponibilidad semanal'
        ordering = ['dia_semana', 'hora_desde']

    def __str__(self):
        return f'{self.psicologo} · {self.get_dia_semana_display()} {self.hora_desde:%H:%M}-{self.hora_hasta:%H:%M}'


class DiaNoAtiende(models.Model):
    """
    Período en el que un psicólogo no atiende (vacaciones, licencia, etc.).
    Tiene prioridad sobre la disponibilidad semanal: mientras una fecha caiga
    en alguno de estos rangos, el turnero público no ofrece nada ese día,
    sin importar lo que diga la plantilla.
    """
    psicologo = models.ForeignKey(
        'profesionales.Psicologo', on_delete=models.CASCADE, related_name='dias_no_atiende'
    )
    fecha_desde = models.DateField(verbose_name='Desde')
    fecha_hasta = models.DateField(verbose_name='Hasta')
    motivo = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Día que no atiende'
        verbose_name_plural = 'Días que no atiende'
        ordering = ['fecha_desde']

    def __str__(self):
        return f'{self.psicologo} · {self.fecha_desde:%d/%m/%Y} — {self.fecha_hasta:%d/%m/%Y}'
