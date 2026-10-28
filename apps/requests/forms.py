from django import forms

from apps.hospitals.models import Hospital

from .models import BloodRequest


class BloodRequestForm(forms.ModelForm):
    """Staff-facing request form. Staff are locked to their own hospital."""

    class Meta:
        model = BloodRequest
        fields = [
            'hospital', 'patient_name', 'blood_group', 'rhesus_factor',
            'quantity_needed', 'urgency_level', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3,
                                           'placeholder': 'Anything the blood bank should know'}),
            'patient_name': forms.TextInput(attrs={'placeholder': 'Optional'}),
            'quantity_needed': forms.NumberInput(attrs={'min': 1, 'step': 1}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['hospital'].queryset = Hospital.objects.active().with_blood_bank()
        if user is not None and user.is_medical_staff and user.hospital_id:
            self.fields['hospital'].initial = user.hospital_id
            self.fields['hospital'].disabled = True

    def clean_quantity_needed(self):
        quantity = self.cleaned_data['quantity_needed']
        if quantity < 1:
            raise forms.ValidationError('Request at least one unit.')
        if quantity > 100:
            raise forms.ValidationError('Requests above 100 units must be raised by an admin.')
        return quantity


class FulfilRequestForm(forms.Form):
    units_fulfilled = forms.IntegerField(min_value=1, label='Units to release from stock')

    def __init__(self, *args, blood_request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.blood_request = blood_request
        if blood_request:
            self.fields['units_fulfilled'].initial = blood_request.units_outstanding
            self.fields['units_fulfilled'].max_value = blood_request.units_outstanding
