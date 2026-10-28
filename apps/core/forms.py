from django import forms

from .models import DonationCriteria


class DonationCriteriaForm(forms.ModelForm):
    class Meta:
        model = DonationCriteria
        fields = ['title', 'content', 'icon', 'order', 'is_active']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': 'One point per line, e.g.\nAged between 18 and 65\nWeigh at least 50kg',
            }),
            'icon': forms.TextInput(attrs={'placeholder': 'e.g. 🩸'}),
        }
