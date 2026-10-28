import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from apps.donations.models import DonationRecord
from apps.inventory.models import BloodInventory
from apps.notifications.emails import send_welcome_email

from .decorators import donor_required, role_home
from .forms import DonorProfileForm, DonorRegistrationForm, EmailAuthenticationForm
from .models import LoginAttempt

logger = logging.getLogger(__name__)

FAILED_KEY = 'failed_login_attempts'
LOCKED_UNTIL_KEY = 'login_locked_until'


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def register(request):
    """Public donor self-registration. No admin approval required."""
    if request.user.is_authenticated:
        return role_home(request.user)

    if request.method == 'POST':
        form = DonorRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
            login(request, user)
            send_welcome_email(user)
            messages.success(
                request,
                f'Welcome, {user.get_full_name()}. Your donor account is ready.',
            )
            return redirect('accounts:dashboard')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = DonorRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


class BDMISLoginView(LoginView):
    """Login for all roles, with a session-based attempt limiter."""

    template_name = 'accounts/login.html'
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def _is_locked(self):
        locked_until = self.request.session.get(LOCKED_UNTIL_KEY)
        if not locked_until:
            return False
        if timezone.now().timestamp() < locked_until:
            return True
        # Cool-down elapsed; reset the counter.
        self.request.session.pop(LOCKED_UNTIL_KEY, None)
        self.request.session[FAILED_KEY] = 0
        return False

    def post(self, request, *args, **kwargs):
        if self._is_locked():
            messages.error(
                request,
                'Too many failed sign-in attempts. Please try again in a few minutes.',
            )
            return self.render_to_response(self.get_context_data(form=self.get_form()))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        self.request.session[FAILED_KEY] = 0
        self.request.session.pop(LOCKED_UNTIL_KEY, None)
        LoginAttempt.objects.create(
            email=form.get_user().email, ip_address=_client_ip(self.request), successful=True
        )
        response = super().form_valid(form)
        messages.success(self.request, f'Signed in as {form.get_user().get_full_name()}.')
        return response

    def form_invalid(self, form):
        attempts = self.request.session.get(FAILED_KEY, 0) + 1
        self.request.session[FAILED_KEY] = attempts
        LoginAttempt.objects.create(
            email=(form.data.get('username') or '')[:254],
            ip_address=_client_ip(self.request),
            successful=False,
        )
        if attempts >= settings.LOGIN_ATTEMPT_LIMIT:
            self.request.session[LOCKED_UNTIL_KEY] = (
                timezone.now().timestamp() + settings.LOGIN_ATTEMPT_COOLDOWN_SECONDS
            )
            messages.error(
                self.request,
                'Too many failed sign-in attempts. This device is locked for 15 minutes.',
            )
        return super().form_invalid(form)

    def get_success_url(self):
        next_url = self.get_redirect_url()
        if next_url:
            return next_url
        return role_home(self.request.user).url


def logout_view(request):
    """Log out on POST (GET logout is unsafe and rejected by Django 5)."""
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'You have been signed out.')
    return redirect('core:home')


@login_required
def dashboard(request):
    """Donor dashboard. Staff and admins are sent to their own landing pages."""
    if not request.user.is_donor:
        return role_home(request.user)

    profile = request.user.donor_profile
    profile.update_eligibility()

    donations = (
        DonationRecord.objects.filter(donor=profile)
        .select_related('hospital')
        .order_by('-donation_date')
    )
    recipient_types = profile.compatible_recipient_types()
    shortages = (
        BloodInventory.objects.shortages()
        .filter(hospital__is_active=True)
        .select_related('hospital')
    )
    matching_shortages = [
        item for item in shortages
        if (item.blood_group, item.rhesus_factor) in recipient_types
    ]

    context = {
        'profile': profile,
        'donations': donations[:10],
        'donation_count': donations.count(),
        'total_units': sum(d.units_donated for d in donations),
        'matching_shortages': matching_shortages,
        'recipient_types': recipient_types,
        'unread_notifications': request.user.donor_profile.notifications.filter(
            is_read=False
        ).count(),
    }
    return render(request, 'accounts/dashboard.html', context)


@donor_required
def profile_view(request):
    """Donors update their own contact details and blood type."""
    profile = request.user.donor_profile
    if request.method == 'POST':
        form = DonorProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('accounts:profile')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = DonorProfileForm(instance=profile)
    return render(request, 'accounts/profile.html', {'form': form, 'profile': profile})
