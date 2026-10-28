from datetime import date

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .constants import BLOOD_GROUP_CHOICES, RHESUS_CHOICES
from .models import DonorProfile, User

MIN_DONOR_AGE = 18
MAX_DONOR_AGE = 65


class DonorRegistrationForm(forms.ModelForm):
    """Public self-registration form. Creates a User plus its DonorProfile."""

    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Chidinma Okeke', 'autofocus': True}),
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'At least 8 characters'}),
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repeat your password'}),
    )
    blood_group = forms.ChoiceField(choices=BLOOD_GROUP_CHOICES)
    rhesus_factor = forms.ChoiceField(choices=RHESUS_CHOICES)
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    phone_number = forms.CharField(
        max_length=15, required=False,
        widget=forms.TextInput(attrs={'placeholder': '0803 000 0000'}),
    )
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))
    city = forms.CharField(max_length=100, required=False,
                           widget=forms.TextInput(attrs={'placeholder': 'Nsukka'}))
    state = forms.CharField(max_length=100, required=False,
                            widget=forms.TextInput(attrs={'placeholder': 'Enugu'}))

    class Meta:
        model = User
        fields = ['full_name', 'username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Choose a username'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('That username is taken.')
        return username

    def clean_date_of_birth(self):
        dob = self.cleaned_data['date_of_birth']
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < MIN_DONOR_AGE:
            raise ValidationError(f'Donors must be at least {MIN_DONOR_AGE} years old.')
        if age > MAX_DONOR_AGE:
            raise ValidationError(f'Donors must be {MAX_DONOR_AGE} years old or younger.')
        return dob

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get('password1'), cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'The two passwords do not match.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.ROLE_DONOR
        user.set_password(self.cleaned_data['password1'])
        user.save()
        # The post_save signal has already created the profile; fill it in.
        profile = user.donor_profile
        profile.blood_group = self.cleaned_data['blood_group']
        profile.rhesus_factor = self.cleaned_data['rhesus_factor']
        profile.date_of_birth = self.cleaned_data['date_of_birth']
        profile.phone_number = self.cleaned_data.get('phone_number', '')
        profile.address = self.cleaned_data.get('address', '')
        profile.city = self.cleaned_data.get('city', '')
        profile.state = self.cleaned_data.get('state', '')
        profile.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    """Login form keyed on email rather than username."""

    username = forms.EmailField(
        label='Email address',
        widget=forms.EmailInput(attrs={'autofocus': True, 'placeholder': 'you@example.com'}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Incorrect email or password.',
    }


class DonorProfileForm(forms.ModelForm):
    """Self-service profile editing. Donors may not change their own eligibility."""

    full_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = DonorProfile
        fields = [
            'blood_group', 'rhesus_factor', 'date_of_birth',
            'phone_number', 'address', 'city', 'state',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['full_name'].initial = self.instance.user.full_name
            # Once a donation is on record the blood type is fixed: stock was
            # credited under it and past records display it.
            if self.instance.donations.exists():
                for name in ('blood_group', 'rhesus_factor'):
                    self.fields[name].disabled = True
                    self.fields[name].help_text = (
                        'Fixed after your first recorded donation. '
                        'Ask the blood bank to correct it if it is wrong.'
                    )

    def save(self, commit=True):
        profile = super().save(commit=commit)
        user = profile.user
        user.full_name = self.cleaned_data.get('full_name', '')
        user.save(update_fields=['full_name'])
        return profile


class StaffUserForm(forms.ModelForm):
    """Admin-side creation and editing of staff / admin accounts."""

    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Leave blank to keep unchanged'}),
        help_text='Required when creating a new account.',
    )

    class Meta:
        model = User
        fields = ['full_name', 'username', 'email', 'role', 'hospital', 'is_active']

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and not cleaned.get('password'):
            self.add_error('password', 'Set a password for the new account.')
        if cleaned.get('role') == User.ROLE_STAFF and not cleaned.get('hospital'):
            self.add_error('hospital', 'Medical staff must be attached to a hospital.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        # Django-admin access follows the application role.
        user.is_staff = user.role == User.ROLE_ADMIN
        if commit:
            user.save()
        return user
