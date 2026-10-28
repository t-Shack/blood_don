"""Notification model and donor-facing alert list."""
from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.hospitals.models import Hospital
from apps.notifications.emails import send_welcome_email
from apps.notifications.models import Notification
from apps.requests.models import BloodRequest

User = get_user_model()


class WelcomeEmailTests(TestCase):
    def test_welcome_email_is_html(self):
        user = User.objects.create_user(
            email='new@example.com', username='new', password='TestPass123!'
        )
        self.assertTrue(send_welcome_email(user))
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(
            any(mime == 'text/html' for _, mime in mail.outbox[0].alternatives)
        )


class NotificationListTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name='Alert Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        self.staff = User.objects.create_user(
            email='staff@example.com', username='staff', password='TestPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital,
        )
        donor_user = User.objects.create_user(
            email='donor@example.com', username='donor', password='TestPass123!'
        )
        self.donor = donor_user.donor_profile
        self.donor.date_of_birth = date(1990, 1, 1)
        self.donor.save()
        self.request = BloodRequest.objects.create(
            hospital=self.hospital, requested_by=self.staff,
            blood_group='O', rhesus_factor='-', quantity_needed=2,
        )
        self.note = Notification.objects.create(
            donor=self.donor, blood_request=self.request, message='Alert sent'
        )

    def test_opening_the_list_marks_alerts_read(self):
        self.client.force_login(self.donor.user)
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_read)

    def test_unread_count_appears_in_context(self):
        self.client.force_login(self.donor.user)
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.context['unread_notification_count'], 1)

    def test_donors_only_see_their_own_alerts(self):
        other = User.objects.create_user(
            email='other@example.com', username='other', password='TestPass123!'
        )
        self.client.force_login(other)
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(len(response.context['notifications']), 0)
