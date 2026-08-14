from django import forms


class ImportarLibrosForm(forms.Form):
    archivo = forms.FileField(label='Archivo Excel (.xlsx)')

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        if not archivo.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('El archivo debe tener extensión .xlsx.')
        return archivo


class ImportarMarcForm(forms.Form):
    archivo = forms.FileField(label='Archivo MARC21 (.mrc o .xml)')

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        nombre = archivo.name.lower()
        if not (nombre.endswith('.mrc') or nombre.endswith('.marc') or nombre.endswith('.xml')):
            raise forms.ValidationError('El archivo debe tener extensión .mrc, .marc o .xml.')
        return archivo
