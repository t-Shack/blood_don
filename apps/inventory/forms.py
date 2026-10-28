from django import forms

from .models import BloodInventory


class BloodInventoryForm(forms.ModelForm):
    class Meta:
        model = BloodInventory
        fields = ['available_units', 'critical_threshold']

    def clean_available_units(self):
        units = self.cleaned_data['available_units']
        if units < 0:
            raise forms.ValidationError('Units cannot be negative.')
        return units

    def clean_critical_threshold(self):
        threshold = self.cleaned_data['critical_threshold']
        if threshold < 0:
            raise forms.ValidationError('Threshold cannot be negative.')
        return threshold


BloodInventoryFormSet = forms.modelformset_factory(
    BloodInventory, form=BloodInventoryForm, extra=0
)
