"""Inventory rows, status thresholds and the public JSON API."""
from django.test import TestCase
from django.urls import reverse

from apps.hospitals.models import Hospital
from apps.inventory.models import BloodInventory


class InventorySetupTests(TestCase):
    def test_new_hospital_with_blood_bank_gets_eight_rows(self):
        hospital = Hospital.objects.create(
            name='Bishop Shanahan', address='Ogurugu Road', city='Nsukka', state='Enugu'
        )
        self.assertEqual(hospital.inventory.count(), 8)

    def test_hospital_without_blood_bank_gets_no_rows(self):
        hospital = Hospital.objects.create(
            name='No Bank Clinic', address='Test Road', city='Nsukka',
            state='Enugu', has_blood_bank=False,
        )
        self.assertEqual(hospital.inventory.count(), 0)

    def test_ensure_for_hospital_is_idempotent(self):
        hospital = Hospital.objects.create(
            name='Idempotent', address='Road', city='Nsukka', state='Enugu'
        )
        BloodInventory.objects.ensure_for_hospital(hospital)
        BloodInventory.objects.ensure_for_hospital(hospital)
        self.assertEqual(hospital.inventory.count(), 8)

    def test_unique_together_is_enforced(self):
        from django.db import IntegrityError, transaction

        hospital = Hospital.objects.create(
            name='Unique Test', address='Road', city='Nsukka', state='Enugu'
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            BloodInventory.objects.create(
                hospital=hospital, blood_group='A', rhesus_factor='+'
            )


class InventoryStatusTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name='Status Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        self.item = self.hospital.inventory.get(blood_group='O', rhesus_factor='-')

    def test_below_threshold_is_critical(self):
        self.item.available_units = 2
        self.assertEqual(self.item.status, 'critical')
        self.assertTrue(self.item.is_in_shortage)

    def test_between_one_and_two_thresholds_is_low(self):
        self.item.available_units = 7
        self.assertEqual(self.item.status, 'low')
        self.assertFalse(self.item.is_in_shortage)

    def test_at_double_threshold_is_sufficient(self):
        self.item.available_units = 10
        self.assertEqual(self.item.status, 'sufficient')

    def test_exactly_at_threshold_is_not_a_shortage(self):
        self.item.available_units = 5
        self.assertFalse(self.item.is_in_shortage)

    def test_add_units_increments_atomically(self):
        self.item.add_units(4)
        self.item.refresh_from_db()
        self.assertEqual(self.item.available_units, 4)

    def test_remove_units_floors_at_zero(self):
        self.item.available_units = 3
        self.item.save()
        removed = self.item.remove_units(10)
        self.assertEqual(removed, 3)
        self.item.refresh_from_db()
        self.assertEqual(self.item.available_units, 0)

    def test_fill_percentage_caps_at_100(self):
        self.item.available_units = 500
        self.assertEqual(self.item.fill_percentage, 100)


class InventoryApiTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name='API Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        item = self.hospital.inventory.get(blood_group='A', rhesus_factor='+')
        item.available_units = 12
        item.save()

    def test_hospital_inventory_endpoint_is_public(self):
        response = self.client.get(
            reverse('api:hospital_inventory', args=[self.hospital.pk])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(len(payload['data']['inventory']), 8)
        self.assertEqual(payload['data']['total_units'], 12)

    def test_envelope_shape(self):
        payload = self.client.get(
            reverse('api:hospital_inventory', args=[self.hospital.pk])
        ).json()
        self.assertEqual(set(payload), {'success', 'data', 'message'})

    def test_unknown_hospital_returns_404_envelope(self):
        response = self.client.get(reverse('api:hospital_inventory', args=[99999]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])

    def test_shortage_endpoint_lists_hospitals(self):
        response = self.client.get(reverse('api:hospitals_in_shortage'))
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['count'], 1)
        self.assertIn('O+', data['hospitals'][0]['shortage_types'])

    def test_eligibility_endpoint_requires_authentication(self):
        response = self.client.get(reverse('api:donor_eligibility'))
        self.assertIn(response.status_code, (401, 403))

    def test_public_inventory_page_renders(self):
        self.assertEqual(self.client.get(reverse('inventory:overview')).status_code, 200)
