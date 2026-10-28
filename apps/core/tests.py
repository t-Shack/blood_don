"""Public pages, the criteria CMS and the seed command."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.core.models import DonationCriteria
from apps.hospitals.models import Hospital

User = get_user_model()


class PublicPageTests(TestCase):
    def test_landing_page_renders(self):
        self.assertEqual(self.client.get(reverse('core:home')).status_code, 200)

    def test_criteria_page_renders_active_sections_only(self):
        DonationCriteria.objects.create(title='Visible', content='One point', order=1)
        DonationCriteria.objects.create(
            title='Hidden', content='Nope', order=2, is_active=False
        )
        response = self.client.get(reverse('core:criteria'))
        titles = [item.title for item in response.context['criteria_list']]
        self.assertEqual(titles, ['Visible'])

    def test_criteria_content_splits_into_points(self):
        item = DonationCriteria.objects.create(
            title='Points', content='First line\n\nSecond line\n', order=1
        )
        self.assertEqual(item.points, ['First line', 'Second line'])

    def test_about_page_renders(self):
        self.assertEqual(self.client.get(reverse('core:about')).status_code, 200)

    def test_404_page(self):
        self.assertEqual(self.client.get('/no-such-page/').status_code, 404)


class SeedCommandTests(TestCase):
    def test_seed_creates_nsukka_hospitals_and_criteria(self):
        call_command('seed_data', verbosity=0)
        self.assertTrue(Hospital.objects.filter(city='Nsukka').exists())
        self.assertTrue(DonationCriteria.objects.exists())
        banked = Hospital.objects.filter(has_blood_bank=True).first()
        self.assertEqual(banked.inventory.count(), 8)

    def test_seed_is_idempotent(self):
        call_command('seed_data', verbosity=0)
        count = Hospital.objects.count()
        call_command('seed_data', verbosity=0)
        self.assertEqual(Hospital.objects.count(), count)


class AdminPanelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@example.com', username='admin', password='TestPass123!'
        )
        self.client.force_login(self.admin)

    def test_dashboard_renders(self):
        self.assertEqual(
            self.client.get(reverse('core:admin_dashboard')).status_code, 200
        )

    def test_adding_a_hospital_creates_inventory_rows(self):
        response = self.client.post(reverse('core:admin_hospital_add'), {
            'name': 'New Hospital', 'address': 'Road', 'city': 'Nsukka',
            'state': 'Enugu', 'phone_number': '08030000000', 'email': '',
            'has_blood_bank': 'on', 'blood_bank_capacity': 100, 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        hospital = Hospital.objects.get(name='New Hospital')
        self.assertEqual(hospital.inventory.count(), 8)

    def test_toggling_deactivates_a_hospital(self):
        hospital = Hospital.objects.create(
            name='Toggle Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        self.client.post(reverse('core:admin_hospital_toggle', args=[hospital.pk]))
        hospital.refresh_from_db()
        self.assertFalse(hospital.is_active)

    def test_criteria_can_be_created_from_the_panel(self):
        response = self.client.post(reverse('core:admin_criteria_add'), {
            'title': 'New section', 'content': 'A point', 'icon': '🩸',
            'order': 1, 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DonationCriteria.objects.filter(title='New section').exists())

    def test_admin_cannot_deactivate_their_own_account(self):
        self.client.post(reverse('core:admin_user_toggle', args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
