from datetime import date, timedelta

from django import forms
from django.conf import settings

from apps.accounts.models import DonorProfile
from apps.hospitals.models import Hospital
from apps.requests.models import BloodRequest

from .models import DonationRecord


class DonationRecordForm(forms.ModelForm):
    """Staff record a physical donation. Enforces the 56-day interval."""

    class Meta:
        model = DonationRecord
        fields = ['donor', 'hospital', 'blood_request', 'donation_date',
                  'units_donated', 'notes']
        widgets = {
            'donation_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'units_donated': forms.NumberInput(attrs={'min': 1, 'max': 1}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['donor'].queryset = DonorProfile.objects.filter(
            user__is_active=True
        ).select_related('user')
        self.fields['hospital'].queryset = Hospital.objects.active().with_blood_bank()
        self.fields['blood_request'].queryset = (
            BloodRequest.objects.pending().select_related('hospital')
        )
        self.fields['blood_request'].required = False
        self.fields['donation_date'].initial = date.today()
        if user is not None and user.is_medical_staff and user.hospital_id:
            # Staff record donations for their own hospital only, as with requests.
            self.fields['hospital'].initial = user.hospital_id
            self.fields['hospital'].disabled = True
            self.fields['blood_request'].queryset = (
                BloodRequest.objects.pending()
                .filter(hospital_id=user.hospital_id)
                .select_related('hospital')
            )

    def clean_donation_date(self):
        donation_date = self.cleaned_data['donation_date']
        if donation_date > date.today():
            raise forms.ValidationError('A donation cannot be recorded for a future date.')
        return donation_date

    def clean_units_donated(self):
        units = self.cleaned_data['units_donated']
        if units < 1:
            raise forms.ValidationError('At least one unit must be recorded.')
        if units > 1:
            # A standard whole blood donation is collected as a single unit.
            raise forms.ValidationError(
                'A whole blood donation is recorded as one unit per session.'
            )
        return units

    def clean(self):
        cleaned = super().clean()
        donor = cleaned.get('donor')
        donation_date = cleaned.get('donation_date')
        interval = settings.DONATION_INTERVAL_DAYS

        if donor and donation_date and donor.last_donation_date:
            gap = (donation_date - donor.last_donation_date).days
            if gap < interval:
                earliest = donor.last_donation_date + timedelta(days=interval)
                self.add_error(
                    'donor',
                    f'{donor.user.get_full_name()} last donated on '
                    f'{donor.last_donation_date:%d %b %Y} and is not eligible until '
                    f'{earliest:%d %b %Y} ({interval}-day interval).',
                )

        blood_request = cleaned.get('blood_request')
        hospital = cleaned.get('hospital')
        if blood_request and hospital and blood_request.hospital_id != hospital.pk:
            self.add_error(
                'blood_request',
                'That request belongs to a different hospital.',
            )
        return cleaned
