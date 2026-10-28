from django import forms

from .models import Hospital


class HospitalForm(forms.ModelForm):
    class Meta:
        model = Hospital
        fields = [
            'name', 'address', 'city', 'state', 'phone_number', 'email',
            'has_blood_bank', 'blood_bank_capacity', 'is_active',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Bishop Shanahan Hospital'}),
            'city': forms.TextInput(attrs={'placeholder': 'Nsukka'}),
            'state': forms.TextInput(attrs={'placeholder': 'Enugu'}),
        }

    def clean_blood_bank_capacity(self):
        capacity = self.cleaned_data['blood_bank_capacity']
        if capacity < 0:
            raise forms.ValidationError('Capacity cannot be negative.')
        return capacity
