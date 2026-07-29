from django import forms

from .models import Paciente, Turno


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
    class Meta:
        model = Turno
        fields = ['paciente', 'fecha_hora', 'estado', 'pagado', 'notas_sesion']
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
