"""Donation recording: inventory increment, eligibility clock, 56-day guard."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.donations.forms import DonationRecordForm
from apps.donations.models import DonationRecord
from apps.hospitals.models import Hospital
from apps.requests.models import BloodRequest

User = get_user_model()


class DonationRecordTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name='Donation Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        self.staff = User.objects.create_user(
            email='staff@example.com', username='staff', password='TestPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital,
        )
        donor_user = User.objects.create_user(
            email='donor@example.com', username='donor', password='TestPass123!'
        )
        self.donor = donor_user.donor_profile
        self.donor.blood_group = 'B'
        self.donor.rhesus_factor = '+'
        self.donor.date_of_birth = date(1992, 3, 3)
        self.donor.save()

    def test_recording_a_donation_increments_inventory(self):
        stock = self.hospital.inventory.get(blood_group='B', rhesus_factor='+')
        self.assertEqual(stock.available_units, 0)

        DonationRecord.objects.create(
            donor=self.donor, hospital=self.hospital,
            donation_date=date.today(), units_donated=2, recorded_by=self.staff,
        )
        stock.refresh_from_db()
        self.assertEqual(stock.available_units, 2)

    def test_units_land_on_the_donors_own_blood_type(self):
        DonationRecord.objects.create(
            donor=self.donor, hospital=self.hospital,
            donation_date=date.today(), units_donated=1, recorded_by=self.staff,
        )
        untouched = self.hospital.inventory.get(blood_group='O', rhesus_factor='-')
        self.assertEqual(untouched.available_units, 0)

    def test_donation_sets_last_donation_date_and_defers_donor(self):
        DonationRecord.objects.create(
            donor=self.donor, hospital=self.hospital,
            donation_date=date.today(), units_donated=1, recorded_by=self.staff,
        )
        self.donor.refresh_from_db()
        self.assertEqual(self.donor.last_donation_date, date.today())
        self.assertFalse(self.donor.is_eligible)
        self.assertEqual(self.donor.next_eligible_date, date.today() + timedelta(days=56))

    def test_backdated_donation_does_not_rewind_the_clock(self):
        self.donor.last_donation_date = date.today() - timedelta(days=10)
        self.donor.save()
        DonationRecord.objects.create(
            donor=self.donor, hospital=self.hospital,
            donation_date=date.today() - timedelta(days=200),
            units_donated=1, recorded_by=self.staff,
        )
        self.donor.refresh_from_db()
        self.assertEqual(self.donor.last_donation_date, date.today() - timedelta(days=10))

    def test_two_donations_accumulate_in_stock(self):
        stock = self.hospital.inventory.get(blood_group='B', rhesus_factor='+')
        for _ in range(2):
            DonationRecord.objects.create(
                donor=self.donor, hospital=self.hospital,
                donation_date=date.today(), units_donated=1, recorded_by=self.staff,
            )
        stock.refresh_from_db()
        self.assertEqual(stock.available_units, 2)

    def test_donation_against_an_open_request_advances_it(self):
        blood_request = BloodRequest.objects.create(
            hospital=self.hospital, requested_by=self.staff,
            blood_group='B', rhesus_factor='+', quantity_needed=1,
        )
        DonationRecord.objects.create(
            donor=self.donor, hospital=self.hospital, blood_request=blood_request,
            donation_date=date.today(), units_donated=1, recorded_by=self.staff,
        )
        blood_request.refresh_from_db()
        self.assertEqual(blood_request.status, BloodRequest.STATUS_FULFILLED)


class DonationFormTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name='Form Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        self.staff = User.objects.create_user(
            email='staff@example.com', username='staff', password='TestPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital,
        )
        donor_user = User.objects.create_user(
            email='donor@example.com', username='donor', password='TestPass123!'
        )
        self.donor = donor_user.donor_profile
        self.donor.date_of_birth = date(1992, 3, 3)
        self.donor.save()

    def _data(self, **overrides):
        data = {
            'donor': self.donor.pk,
            'hospital': self.hospital.pk,
            'donation_date': date.today().isoformat(),
            'units_donated': 1,
            'notes': '',
        }
        data.update(overrides)
        return data

    def test_valid_donation_is_accepted(self):
        form = DonationRecordForm(self._data(), user=self.staff)
        self.assertTrue(form.is_valid(), form.errors)

    def test_donation_inside_56_days_is_rejected(self):
        self.donor.last_donation_date = date.today() - timedelta(days=20)
        self.donor.save()
        form = DonationRecordForm(self._data(), user=self.staff)
        self.assertFalse(form.is_valid())
        self.assertIn('donor', form.errors)

    def test_donation_after_56_days_is_accepted(self):
        self.donor.last_donation_date = date.today() - timedelta(days=56)
        self.donor.save()
        form = DonationRecordForm(self._data(), user=self.staff)
        self.assertTrue(form.is_valid(), form.errors)

    def test_future_dated_donation_is_rejected(self):
        form = DonationRecordForm(
            self._data(donation_date=(date.today() + timedelta(days=1)).isoformat()),
            user=self.staff,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('donation_date', form.errors)

    def test_zero_units_is_rejected(self):
        form = DonationRecordForm(self._data(units_donated=0), user=self.staff)
        self.assertFalse(form.is_valid())

    def test_donor_cannot_open_the_recording_page(self):
        self.client.force_login(self.donor.user)
        self.assertEqual(self.client.get(reverse('donations:record')).status_code, 403)
