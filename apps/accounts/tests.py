"""Tests for the custom user model, donor profiles and role-based access."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.constants import compatible_donors_for, compatible_recipients_for
from apps.accounts.models import DonorProfile
from apps.donations.models import DonationRecord
from apps.hospitals.models import Hospital

User = get_user_model()


def make_donor(email='donor@example.com', group='O', rhesus='-', **kwargs):
    user = User.objects.create_user(
        email=email, username=email.split('@')[0], password='TestPass123!'
    )
    profile = user.donor_profile
    profile.blood_group = group
    profile.rhesus_factor = rhesus
    profile.date_of_birth = date(1995, 5, 20)
    for key, value in kwargs.items():
        setattr(profile, key, value)
    profile.save()
    return user, profile


class UserModelTests(TestCase):
    def test_donor_profile_created_by_signal(self):
        user = User.objects.create_user(
            email='new@example.com', username='new', password='TestPass123!'
        )
        self.assertTrue(DonorProfile.objects.filter(user=user).exists())

    def test_staff_account_gets_no_donor_profile(self):
        user = User.objects.create_user(
            email='staff@example.com', username='staff',
            password='TestPass123!', role=User.ROLE_STAFF,
        )
        self.assertFalse(DonorProfile.objects.filter(user=user).exists())

    def test_superuser_is_administrator(self):
        admin = User.objects.create_superuser(
            email='root@example.com', username='root', password='TestPass123!'
        )
        self.assertTrue(admin.is_administrator)
        self.assertTrue(admin.is_staff)

    def test_email_is_the_login_field(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')


class EligibilityTests(TestCase):
    def test_donor_with_no_history_is_eligible(self):
        _, profile = make_donor()
        self.assertTrue(profile.update_eligibility())
        self.assertIsNone(profile.next_eligible_date)

    def test_donation_inside_56_days_makes_donor_ineligible(self):
        _, profile = make_donor(last_donation_date=date.today() - timedelta(days=10))
        profile.update_eligibility()
        self.assertFalse(profile.is_eligible)
        self.assertEqual(profile.days_until_eligible, 46)

    def test_donor_becomes_eligible_on_day_56(self):
        _, profile = make_donor(last_donation_date=date.today() - timedelta(days=56))
        profile.update_eligibility()
        self.assertTrue(profile.is_eligible)

    def test_donor_still_deferred_on_day_55(self):
        _, profile = make_donor(last_donation_date=date.today() - timedelta(days=55))
        profile.update_eligibility()
        self.assertFalse(profile.is_eligible)

    def test_next_eligible_date_is_56_days_after_donation(self):
        last = date.today() - timedelta(days=10)
        _, profile = make_donor(last_donation_date=last)
        self.assertEqual(profile.next_eligible_date, last + timedelta(days=56))

    def test_management_command_flips_eligibility_back(self):
        from django.core.management import call_command

        _, profile = make_donor(last_donation_date=date.today() - timedelta(days=100))
        DonorProfile.objects.filter(pk=profile.pk).update(is_eligible=False)
        call_command('update_donor_eligibility', verbosity=0)
        profile.refresh_from_db()
        self.assertTrue(profile.is_eligible)


class CompatibilityMatrixTests(TestCase):
    """The medically critical part: every one of the eight recipient types."""

    def test_a_positive_recipient(self):
        self.assertCountEqual(
            compatible_donors_for('A', '+'),
            [('A', '+'), ('A', '-'), ('O', '+'), ('O', '-')],
        )

    def test_a_negative_recipient(self):
        self.assertCountEqual(compatible_donors_for('A', '-'), [('A', '-'), ('O', '-')])

    def test_b_positive_recipient(self):
        self.assertCountEqual(
            compatible_donors_for('B', '+'),
            [('B', '+'), ('B', '-'), ('O', '+'), ('O', '-')],
        )

    def test_b_negative_recipient(self):
        self.assertCountEqual(compatible_donors_for('B', '-'), [('B', '-'), ('O', '-')])

    def test_ab_positive_is_universal_recipient(self):
        self.assertEqual(len(compatible_donors_for('AB', '+')), 8)

    def test_ab_negative_recipient(self):
        self.assertCountEqual(
            compatible_donors_for('AB', '-'),
            [('A', '-'), ('B', '-'), ('AB', '-'), ('O', '-')],
        )

    def test_o_positive_recipient(self):
        self.assertCountEqual(compatible_donors_for('O', '+'), [('O', '+'), ('O', '-')])

    def test_o_negative_recipient_takes_only_o_negative(self):
        self.assertEqual(compatible_donors_for('O', '-'), [('O', '-')])

    def test_o_negative_is_universal_donor(self):
        self.assertEqual(len(compatible_recipients_for('O', '-')), 8)

    def test_ab_positive_donor_gives_only_to_ab_positive(self):
        self.assertEqual(compatible_recipients_for('AB', '+'), [('AB', '+')])

    def test_a_negative_donor_recipients(self):
        self.assertCountEqual(
            compatible_recipients_for('A', '-'),
            [('A', '-'), ('A', '+'), ('AB', '-'), ('AB', '+')],
        )

    def test_matrix_is_symmetric_with_recipient_lookup(self):
        """Every donor->recipient claim must agree with the recipient->donor table."""
        from apps.accounts.constants import BLOOD_TYPES
        for donor in BLOOD_TYPES:
            for recipient in compatible_recipients_for(*donor):
                self.assertIn(donor, compatible_donors_for(*recipient))


class RegistrationViewTests(TestCase):
    def test_registration_creates_active_donor_and_logs_in(self):
        response = self.client.post(reverse('accounts:register'), {
            'full_name': 'Chidinma Okeke',
            'username': 'chidinma',
            'email': 'chidinma@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'blood_group': 'O',
            'rhesus_factor': '-',
            'date_of_birth': '1996-04-12',
            'phone_number': '08030000000',
            'city': 'Nsukka',
            'state': 'Enugu',
        })
        self.assertRedirects(response, reverse('accounts:dashboard'))
        user = User.objects.get(email='chidinma@example.com')
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, User.ROLE_DONOR)
        self.assertEqual(user.donor_profile.full_blood_type, 'O-')

    def test_under_18_is_rejected(self):
        too_young = date.today() - timedelta(days=365 * 15)
        response = self.client.post(reverse('accounts:register'), {
            'full_name': 'Too Young', 'username': 'young',
            'email': 'young@example.com',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
            'blood_group': 'A', 'rhesus_factor': '+',
            'date_of_birth': too_young.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='young@example.com').exists())

    def test_mismatched_passwords_rejected(self):
        response = self.client.post(reverse('accounts:register'), {
            'full_name': 'Mismatch', 'username': 'mismatch',
            'email': 'mismatch@example.com',
            'password1': 'StrongPass123!', 'password2': 'DifferentPass123!',
            'blood_group': 'A', 'rhesus_factor': '+',
            'date_of_birth': '1990-01-01',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='mismatch@example.com').exists())


class RoleAccessTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name='Test Hospital', address='1 Test Road', city='Nsukka', state='Enugu'
        )
        self.donor_user, self.donor_profile = make_donor()
        self.staff = User.objects.create_user(
            email='staff@example.com', username='staffuser', password='TestPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital,
        )
        self.admin = User.objects.create_superuser(
            email='admin@example.com', username='adminuser', password='TestPass123!'
        )

    def test_donor_cannot_reach_request_creation(self):
        self.client.force_login(self.donor_user)
        response = self.client.get(reverse('requests:create'))
        self.assertEqual(response.status_code, 403)

    def test_donor_cannot_reach_admin_panel(self):
        self.client.force_login(self.donor_user)
        response = self.client.get(reverse('core:admin_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_reach_admin_panel(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('core:admin_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_reach_request_creation(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('requests:create')).status_code, 200)

    def test_admin_can_reach_admin_panel(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('core:admin_dashboard')).status_code, 200)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_staff_cannot_reach_donor_profile_page(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('accounts:profile')).status_code, 403)

    def test_donation_history_is_scoped_to_the_donor(self):
        other_user, other_profile = make_donor(email='other@example.com', group='A')
        DonationRecord.objects.create(
            donor=other_profile, hospital=self.hospital,
            donation_date=date.today(), units_donated=1, recorded_by=self.staff,
        )
        self.client.force_login(self.donor_user)
        response = self.client.get(reverse('donations:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['donations']), 0)
