from django import forms


class ImportarLibrosForm(forms.Form):
    archivo = forms.FileField(label='Archivo Excel (.xlsx)')

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        if not archivo.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('El archivo debe tener extensión .xlsx.')
        return archivo
