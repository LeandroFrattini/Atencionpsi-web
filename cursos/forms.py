from django import forms


class InscripcionPublicaForm(forms.Form):
    nombre = forms.CharField(label='Nombre y apellido', max_length=150)
    email = forms.EmailField(label='Email')
    whatsapp = forms.CharField(label='WhatsApp', max_length=30)
