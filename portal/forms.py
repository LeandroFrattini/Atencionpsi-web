from django import forms

from profesionales.models import Psicologo

from .models import DiaNoAtiende, DisponibilidadSemanal, Gasto, Pago, Paciente, Turno


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ['psicologo', 'fecha', 'monto', 'concepto']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'concepto': forms.TextInput(attrs={'placeholder': 'Ej: Alta, mensualidad agosto'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['psicologo'].queryset = Psicologo.objects.order_by('nombre')
        self.fields['psicologo'].required = False


class GastoForm(forms.ModelForm):
    class Meta:
        model = Gasto
        fields = ['fecha', 'monto', 'concepto']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'concepto': forms.TextInput(attrs={'placeholder': 'Ej: Hosting, publicidad'}),
        }


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            'nombre', 'apellido', 'dni', 'telefono', 'email', 'fecha_nacimiento', 'activo',
            'motivo_consulta', 'antecedentes', 'diagnostico', 'tratamiento', 'notas_generales',
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'motivo_consulta': forms.Textarea(attrs={'rows': 3}),
            'antecedentes': forms.Textarea(attrs={'rows': 3}),
            'diagnostico': forms.Textarea(attrs={'rows': 3}),
            'tratamiento': forms.Textarea(attrs={'rows': 3}),
            'notas_generales': forms.Textarea(attrs={'rows': 3}),
        }


class TurnoForm(forms.ModelForm):
    recurrente = forms.BooleanField(
        required=False,
        label='Turno recurrente',
        help_text='Vas a reservar todo el mes: el mismo día, a la misma hora, durante 4 semanas.',
    )

    class Meta:
        model = Turno
        fields = ['paciente', 'fecha_hora', 'estado', 'modalidad', 'pagado', 'notas_sesion']
        widgets = {
            'fecha_hora': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'notas_sesion': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, psico=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_hora'].input_formats = ['%Y-%m-%dT%H:%M']
        # Crítico: el paciente elegible SIEMPRE se restringe a los del propio
        # psicólogo, para que no se pueda crear/editar un turno apuntando al
        # paciente de otro profesional aunque se manipule el POST.
        if psico is not None:
            self.fields['paciente'].queryset = Paciente.objects.filter(psicologo=psico, activo=True)


class DisponibilidadBloqueForm(forms.ModelForm):
    class Meta:
        model = DisponibilidadSemanal
        fields = ['dia_semana', 'hora_desde', 'hora_hasta', 'modalidad']
        widgets = {
            'hora_desde': forms.TimeInput(attrs={'type': 'time'}),
            'hora_hasta': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned = super().clean()
        desde, hasta = cleaned.get('hora_desde'), cleaned.get('hora_hasta')
        if desde and hasta and desde >= hasta:
            raise forms.ValidationError('La hora de inicio tiene que ser antes que la de fin.')
        return cleaned


class DiaNoAtiendeForm(forms.ModelForm):
    class Meta:
        model = DiaNoAtiende
        fields = ['fecha_desde', 'fecha_hasta', 'motivo']
        widgets = {
            'fecha_desde': forms.DateInput(attrs={'type': 'date'}),
            'fecha_hasta': forms.DateInput(attrs={'type': 'date'}),
            'motivo': forms.TextInput(attrs={'placeholder': 'Opcional, ej: Vacaciones'}),
        }

    def clean(self):
        cleaned = super().clean()
        desde, hasta = cleaned.get('fecha_desde'), cleaned.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            raise forms.ValidationError('La fecha "desde" tiene que ser antes (o igual) que "hasta".')
        return cleaned


class DisponibilidadSettingsForm(forms.ModelForm):
    class Meta:
        model = Psicologo
        fields = ['duracion_turno_min', 'direccion_consultorio']


class ReservaPublicaForm(forms.Form):
    nombre = forms.CharField(max_length=100)
    apellido = forms.CharField(max_length=100)
    email = forms.EmailField()
    telefono = forms.CharField(max_length=30)
    fecha_nacimiento = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
