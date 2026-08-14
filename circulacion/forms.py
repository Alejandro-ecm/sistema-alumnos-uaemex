from django import forms


class PrestamoForm(forms.Form):
    alumno_nombre = forms.CharField(max_length=200, label='Nombre del alumno')
    matricula = forms.CharField(max_length=20, required=False, label='Matrícula')
    telefono = forms.CharField(max_length=20, required=False, label='Teléfono')
    carrera = forms.CharField(max_length=150, required=False, label='Carrera')
    fecha_salida = forms.DateField(label='Fecha de salida')
    fecha_devolucion = forms.DateField(label='Fecha de devolución')
    observaciones = forms.CharField(required=False, widget=forms.Textarea, label='Observaciones')
    ejemplares = forms.CharField(widget=forms.HiddenInput, label='Libros')

    def clean_ejemplares(self):
        crudo = self.cleaned_data['ejemplares']
        ids = [int(valor) for valor in crudo.split(',') if valor.strip().isdigit()]
        if not ids:
            raise forms.ValidationError('Agrega al menos un libro al préstamo.')
        return ids

    def clean(self):
        cleaned = super().clean()
        salida = cleaned.get('fecha_salida')
        devolucion = cleaned.get('fecha_devolucion')
        if salida and devolucion and devolucion < salida:
            raise forms.ValidationError('La fecha de devolución no puede ser anterior a la fecha de salida.')
        return cleaned


class DevolucionForm(forms.Form):
    multa_descuento = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0, required=False, initial=0,
        label='Descuento aplicado',
    )
    multa_cobrada = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0, required=False, initial=0,
        label='Monto cobrado',
    )
    multa_pagada = forms.BooleanField(required=False, label='Multa pagada')

    def clean_multa_descuento(self):
        return self.cleaned_data['multa_descuento'] or 0

    def clean_multa_cobrada(self):
        return self.cleaned_data['multa_cobrada'] or 0
