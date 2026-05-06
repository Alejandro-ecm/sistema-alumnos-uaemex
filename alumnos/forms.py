from django import forms
from .models import Alumno

class AlumnoForm(forms.ModelForm):
    acepta_terminos = forms.BooleanField(
        required=True,
        label='Entiendo / Acepto los términos y condiciones',
        error_messages={'required': 'Debes aceptar los términos y condiciones para continuar.'}
    )

    class Meta:
        model = Alumno
        exclude = ['estado', 'fecha_registro', 'facultad', 'semestre', 'tema', 'director']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'APELLIDOS NOMBRE(S)', 'style': 'text-transform:uppercase'}),
            'numero_cuenta': forms.TextInput(attrs={'placeholder': 'Ej. 1234567'}),
            'correo': forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Ej. 7221234567'}),
            'domicilio': forms.TextInput(attrs={'placeholder': 'Calle, colonia, municipio, C.P.'}),
            'carrera': forms.Select(),
            'modalidad': forms.Select(),
            'documento1': forms.ClearableFileInput(),
            'documento2': forms.ClearableFileInput(),
            'documento3': forms.ClearableFileInput(),
        }


