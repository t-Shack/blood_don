"""Regression tests for the five defects found during system testing."""
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import DonorProfileForm
from apps.accounts.models import User
from apps.donations.forms import DonationRecordForm
from apps.donations.models import DonationRecord
from apps.hospitals.models import Hospital
from apps.inventory.models import BloodInventory


class RegressionTests(TestCase):
    def setUp(self):
        self.hospital_a = Hospital.objects.create(
            name='Alpha Hospital', address='1 Road', city='Nsukka', state='Enugu')
        self.hospital_b = Hospital.objects.create(
            name='Beta Hospital', address='2 Road', city='Nsukka', state='Enugu')
        self.staff = User.objects.create_user(
            email='staff@test.ng', username='staff', password='StaffPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital_a)
        donor_user = User.objects.create_user(
            email='donor@test.ng', username='donor', password='DonorPass123!',
            full_name='Test Donor')
        self.donor = donor_user.donor_profile
        self.donor.blood_group, self.donor.rhesus_factor = 'A', '-'
        self.donor.date_of_birth = date(1995, 5, 17)
        self.donor.save()

    def test_stock_changes_refresh_last_updated(self):
        item = BloodInventory.objects.get(
            hospital=self.hospital_a, blood_group='A', rhesus_factor='-')
        old = timezone.now() - timedelta(days=3)
        for change in (lambda: item.add_units(2), lambda: item.remove_units(1)):
            BloodInventory.objects.filter(pk=item.pk).update(last_updated=old)
            item.refresh_from_db()
            change()
            self.assertGreater(item.last_updated, old + timedelta(days=2))

    def test_shortage_api_reports_blood_type_count(self):
        self.hospital_b.is_active = False
        self.hospital_b.save()
        rows = list(BloodInventory.objects.filter(hospital=self.hospital_a).ordered())
        for item in rows[:6]:
            BloodInventory.objects.filter(pk=item.pk).update(available_units=20)
        data = self.client.get(reverse('api:hospitals_in_shortage')).json()['data']
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['type_count'], 2)

    def test_staff_donation_is_locked_to_their_hospital(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('donations:record'), {
            'donor': self.donor.pk, 'hospital': self.hospital_b.pk,
            'donation_date': date.today().isoformat(), 'units_donated': 1, 'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DonationRecord.objects.get().hospital, self.hospital_a)

    def test_blood_type_is_fixed_after_first_donation(self):
        DonationRecord.objects.create(
            donor=self.donor, hospital=self.hospital_a, donation_date=date.today(),
            units_donated=1, recorded_by=self.staff)
        form = DonorProfileForm(data={
            'full_name': 'Test Donor', 'blood_group': 'AB', 'rhesus_factor': '+',
            'date_of_birth': '1995-05-17', 'phone_number': '', 'address': '',
            'city': '', 'state': '',
        }, instance=self.donor)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.donor.refresh_from_db()
        self.assertEqual(self.donor.full_blood_type, 'A-')

    def test_one_unit_per_donation_session(self):
        form = DonationRecordForm(data={
            'donor': self.donor.pk, 'hospital': self.hospital_a.pk,
            'donation_date': date.today().isoformat(), 'units_donated': 2, 'notes': '',
        }, user=self.staff)
        self.assertFalse(form.is_valid())
        self.assertIn('units_donated', form.errors)


class DeploymentTests(TestCase):
    """The Render deploy returned 400 Bad Request for every page."""

    def test_health_check_ignores_host_and_database(self):
        # Render's checker may send an internal Host header over plain http.
        response = self.client.get('/healthz', HTTP_HOST='10.0.0.5:10000')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_production_strips_scheme_from_allowed_hosts(self):
        from bdmis.settings.production import _bare_host
        self.assertEqual(_bare_host('https://blood-don-f9c4.onrender.com/'),
                         'blood-don-f9c4.onrender.com')
        self.assertEqual(_bare_host(' localhost '), 'localhost')
