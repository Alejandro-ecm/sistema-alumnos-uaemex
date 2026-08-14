from django import forms
from .models import Alumno

class AlumnoForm(forms.ModelForm):
    DOMINIOS_INSTITUCIONALES = ['alumno.uaemex.mx']

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
            'correo': forms.EmailInput(attrs={'placeholder': 'nombre@alumno.uaemex.mx'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Ej. 7221234567'}),
            'domicilio': forms.TextInput(attrs={'placeholder': 'Calle, colonia, municipio, C.P.'}),
            'carrera': forms.Select(),
            'modalidad': forms.Select(),
            'documento1': forms.ClearableFileInput(attrs={'accept': 'application/pdf'}),
            'documento2': forms.ClearableFileInput(attrs={'accept': 'application/pdf'}),
            'documento3': forms.ClearableFileInput(attrs={'accept': 'application/pdf'}),
            'libro_titulo': forms.TextInput(attrs={'placeholder': 'Título del libro'}),
            'libro_autor': forms.TextInput(attrs={'placeholder': 'Autor(es) del libro'}),
            'libro_editorial': forms.TextInput(attrs={'placeholder': 'Editorial'}),
            'libro_edicion': forms.TextInput(attrs={'placeholder': 'Ej. 3a edición'}),
            'libro_portada': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ('libro_titulo', 'libro_autor', 'libro_editorial', 'libro_edicion', 'libro_portada'):
            self.fields[campo].required = True
        self.fields['correo'].required = True

    def clean_correo(self):
        correo = (self.cleaned_data.get('correo') or '').strip()
        dominio = correo.rsplit('@', 1)[-1].lower() if '@' in correo else ''
        if dominio not in self.DOMINIOS_INSTITUCIONALES:
            raise forms.ValidationError(
                'Debes usar tu correo institucional (@alumno.uaemex.mx), no un correo personal.'
            )
        return correo


