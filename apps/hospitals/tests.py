"""Hospital directory: slugs, filtering and shortage reporting."""
from django.test import TestCase
from django.urls import reverse

from apps.hospitals.models import Hospital


class HospitalModelTests(TestCase):
    def test_slug_is_generated_and_unique(self):
        first = Hospital.objects.create(
            name='General Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        second = Hospital.objects.create(
            name='General Hospital', address='Other Road', city='Nsukka', state='Enugu'
        )
        self.assertEqual(first.slug, 'general-hospital-nsukka')
        self.assertNotEqual(first.slug, second.slug)

    def test_total_units_sums_inventory(self):
        hospital = Hospital.objects.create(
            name='Sum Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        for item in hospital.inventory.all()[:3]:
            item.available_units = 5
            item.save()
        self.assertEqual(hospital.total_units, 15)

    def test_shortage_types_lists_only_critical_ones(self):
        hospital = Hospital.objects.create(
            name='Shortage Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        for item in hospital.inventory.all():
            item.available_units = 20
            item.save()
        low = hospital.inventory.get(blood_group='AB', rhesus_factor='-')
        low.available_units = 1
        low.save()
        self.assertEqual(hospital.shortage_types(), ['AB-'])
        self.assertTrue(hospital.is_in_shortage)

    def test_capacity_percentage_handles_zero_capacity(self):
        hospital = Hospital.objects.create(
            name='No Capacity', address='Road', city='Nsukka', state='Enugu',
            blood_bank_capacity=0,
        )
        self.assertEqual(hospital.capacity_percentage, 0)


class HospitalViewTests(TestCase):
    def setUp(self):
        self.active = Hospital.objects.create(
            name='Active Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        self.inactive = Hospital.objects.create(
            name='Closed Hospital', address='Road', city='Nsukka',
            state='Enugu', is_active=False,
        )
        self.other_city = Hospital.objects.create(
            name='Enugu City Hospital', address='Road', city='Enugu', state='Enugu'
        )

    def test_directory_hides_inactive_hospitals(self):
        response = self.client.get(reverse('hospitals:list'))
        names = [h.name for h in response.context['hospitals']]
        self.assertIn('Active Hospital', names)
        self.assertNotIn('Closed Hospital', names)

    def test_city_filter(self):
        response = self.client.get(reverse('hospitals:list'), {'city': 'Nsukka'})
        self.assertEqual(len(response.context['hospitals']), 1)

    def test_search_by_name(self):
        response = self.client.get(reverse('hospitals:list'), {'q': 'Enugu City'})
        self.assertEqual(len(response.context['hospitals']), 1)

    def test_detail_page_renders(self):
        self.assertEqual(
            self.client.get(self.active.get_absolute_url()).status_code, 200
        )

    def test_inactive_hospital_detail_is_404(self):
        response = self.client.get(
            reverse('hospitals:detail', args=[self.inactive.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_inventory_page_renders(self):
        response = self.client.get(reverse('hospitals:inventory', args=[self.active.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['inventory']), 8)
