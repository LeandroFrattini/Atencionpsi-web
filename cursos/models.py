from django.db import models


class Curso(models.Model):
    """Un curso/taller puntual de Formación (no un turno de terapia).
    Tiene dos precios porque el cobro es distinto para un profesional que
    ya está en la Red Consulta (logueado, precio de red) que para el
    público general (sin cuenta, precio de lista)."""
    nombre = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    descripcion = models.TextField(blank=True, help_text='Se muestra en la página pública del curso.')
    presentador = models.CharField(max_length=150)
    presentador_detalle = models.CharField(
        max_length=150, blank=True,
        help_text='Ej: "Esp. en Psicología Clínica · UBA"'
    )
    presentador_bio = models.TextField(
        blank=True,
        help_text='Bio corta con formación/experiencia del presentador -- se muestra '
                   'en un popup al hacer click en su nombre, para darle credibilidad. '
                   'Vacío = el nombre no es clickeable.'
    )
    presentador_foto = models.ImageField(upload_to='cursos/presentadores/', null=True, blank=True)
    fecha = models.DateField()
    hora = models.TimeField()
    precio_red_consulta = models.DecimalField('Precio Red Consulta', max_digits=10, decimal_places=2)
    precio_publico = models.DecimalField('Precio público general', max_digits=10, decimal_places=2)
    cupo_maximo = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Vacío = sin límite. Cuenta solo las inscripciones ya pagadas.'
    )
    activo = models.BooleanField(default=True, help_text='Si está apagado, la página pública da 404.')

    class Meta:
        verbose_name = 'Curso / Taller'
        verbose_name_plural = 'Cursos / Talleres'
        ordering = ['fecha']

    def __str__(self):
        return f'{self.nombre} ({self.fecha:%d/%m/%Y})'

    @property
    def inscripciones_aprobadas(self):
        return self.inscripciones.filter(estado='aprobado').count()

    @property
    def cupos_disponibles(self):
        """None significa sin límite -- distinto de 0 (agotado)."""
        if self.cupo_maximo is None:
            return None
        return max(0, self.cupo_maximo - self.inscripciones_aprobadas)

    @property
    def agotado(self):
        return self.cupos_disponibles == 0


class InscripcionCurso(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de pago'),
        ('aprobado', 'Pagado'),
        ('rechazado', 'Rechazado / cancelado'),
    ]

    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name='inscripciones')
    # Solo se completa cuando se inscribe por el camino de Red Consulta (con
    # login) -- una inscripción de público general no tiene profesional
    # asociado, es gente que todavía no tiene cuenta en el portal.
    psicologo = models.ForeignKey(
        'profesionales.Psicologo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='inscripciones_cursos',
    )
    nombre = models.CharField(max_length=150)
    email = models.EmailField()
    whatsapp = models.CharField(max_length=30)
    es_red_consulta = models.BooleanField(default=False)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    mp_preference_id = models.CharField(max_length=100, blank=True)
    mp_payment_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_aprobado = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Inscripción'
        verbose_name_plural = 'Inscripciones'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.nombre} -> {self.curso.nombre} ({self.get_estado_display()})'

    def marcar_aprobado(self, mp_payment_id=''):
        """Idempotente: si ya estaba aprobado (ej. el webhook llega dos
        veces, algo normal en Mercado Pago) no vuelve a pisar la fecha ni
        reenvía el mail de confirmación -- eso lo decide quien llama a
        esto mirando el valor de retorno."""
        ya_estaba_aprobado = self.estado == 'aprobado'
        if mp_payment_id:
            self.mp_payment_id = mp_payment_id
        if not ya_estaba_aprobado:
            from django.utils import timezone
            self.estado = 'aprobado'
            self.fecha_aprobado = timezone.now()
        self.save()
        return not ya_estaba_aprobado
