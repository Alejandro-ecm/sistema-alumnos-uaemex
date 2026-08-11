from django import forms


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
