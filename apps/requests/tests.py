"""Blood request fulfilment, compatibility and the notification dispatch."""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import DonorProfile
from apps.hospitals.models import Hospital
from apps.notifications.dispatch import (
    dispatch_blood_request_notifications,
    eligible_compatible_donors,
)
from apps.notifications.models import Notification
from apps.requests.models import BloodRequest

User = get_user_model()


def make_donor(email, group, rhesus, eligible=True, active=True):
    user = User.objects.create_user(
        email=email, username=email.split('@')[0], password='TestPass123!'
    )
    if not active:
        user.is_active = False
        user.save(update_fields=['is_active'])
    profile = user.donor_profile
    profile.blood_group = group
    profile.rhesus_factor = rhesus
    profile.date_of_birth = date(1990, 1, 1)
    if not eligible:
        profile.last_donation_date = date.today() - timedelta(days=5)
    profile.save()
    profile.update_eligibility()
    return profile


class RequestFulfilmentTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name='Request Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        self.staff = User.objects.create_user(
            email='staff@example.com', username='staff', password='TestPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital,
        )
        self.stock = self.hospital.inventory.get(blood_group='A', rhesus_factor='+')

    def _make_request(self, quantity=3, group='A', rhesus='+'):
        return BloodRequest.objects.create(
            hospital=self.hospital, requested_by=self.staff,
            blood_group=group, rhesus_factor=rhesus, quantity_needed=quantity,
        )

    def test_sufficient_stock_fulfils_and_decrements(self):
        self.stock.available_units = 10
        self.stock.save()
        request = self._make_request(quantity=3)
        taken = request.try_fulfil_from_stock()
        self.assertEqual(taken, 3)
        self.assertEqual(request.status, BloodRequest.STATUS_FULFILLED)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.available_units, 7)

    def test_partial_stock_leaves_request_pending(self):
        self.stock.available_units = 2
        self.stock.save()
        request = self._make_request(quantity=5)
        taken = request.try_fulfil_from_stock()
        self.assertEqual(taken, 2)
        self.assertEqual(request.status, BloodRequest.STATUS_PENDING)
        self.assertEqual(request.units_outstanding, 3)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.available_units, 0)

    def test_no_stock_takes_nothing(self):
        request = self._make_request(quantity=4)
        self.assertEqual(request.try_fulfil_from_stock(), 0)
        self.assertEqual(request.status, BloodRequest.STATUS_PENDING)

    def test_fulfilment_never_draws_a_different_blood_type(self):
        other = self.hospital.inventory.get(blood_group='O', rhesus_factor='-')
        other.available_units = 50
        other.save()
        request = self._make_request(quantity=3, group='A', rhesus='+')
        self.assertEqual(request.try_fulfil_from_stock(), 0)
        other.refresh_from_db()
        self.assertEqual(other.available_units, 50)

    def test_cancel_closes_the_request(self):
        request = self._make_request()
        request.cancel()
        self.assertEqual(request.status, BloodRequest.STATUS_CANCELLED)
        self.assertFalse(request.is_open)

    def test_staff_submission_flow_decrements_stock(self):
        self.stock.available_units = 8
        self.stock.save()
        self.client.force_login(self.staff)
        response = self.client.post(reverse('requests:create'), {
            'hospital': self.hospital.pk, 'patient_name': 'Test Patient',
            'blood_group': 'A', 'rhesus_factor': '+',
            'quantity_needed': 3, 'urgency_level': 'medium', 'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        request = BloodRequest.objects.get()
        self.assertEqual(request.status, BloodRequest.STATUS_FULFILLED)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.available_units, 5)

    def test_api_fulfil_endpoint(self):
        self.stock.available_units = 6
        self.stock.save()
        request = self._make_request(quantity=4)
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('api:fulfil_request', args=[request.pk]),
            {'units_fulfilled': 2}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['units_fulfilled'], 2)
        self.assertEqual(data['units_outstanding'], 2)

    def test_api_fulfil_rejects_donors(self):
        request = self._make_request()
        donor = make_donor('donor@example.com', 'A', '+')
        self.client.force_login(donor.user)
        response = self.client.post(
            reverse('api:fulfil_request', args=[request.pk]),
            {'units_fulfilled': 1}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)


class NotificationDispatchTests(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name='Alert Hospital', address='Road', city='Nsukka', state='Enugu'
        )
        self.staff = User.objects.create_user(
            email='staff2@example.com', username='staff2', password='TestPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital,
        )

    def _request_for(self, group, rhesus, quantity=5):
        return BloodRequest.objects.create(
            hospital=self.hospital, requested_by=self.staff,
            blood_group=group, rhesus_factor=rhesus, quantity_needed=quantity,
        )

    def test_only_compatible_donors_are_selected(self):
        make_donor('o_neg@example.com', 'O', '-')
        make_donor('a_neg@example.com', 'A', '-')
        make_donor('a_pos@example.com', 'A', '+')
        make_donor('b_pos@example.com', 'B', '+')

        donors = eligible_compatible_donors(self._request_for('A', '-'))
        emails = {donor.user.email for donor in donors}
        self.assertEqual(emails, {'o_neg@example.com', 'a_neg@example.com'})

    def test_ab_positive_request_reaches_every_type(self):
        for index, (group, rhesus) in enumerate(
            [('A', '+'), ('A', '-'), ('B', '+'), ('B', '-'),
             ('AB', '+'), ('AB', '-'), ('O', '+'), ('O', '-')]
        ):
            make_donor(f'donor{index}@example.com', group, rhesus)
        donors = eligible_compatible_donors(self._request_for('AB', '+'))
        self.assertEqual(len(donors), 8)

    def test_o_negative_request_reaches_only_o_negative(self):
        make_donor('o_neg@example.com', 'O', '-')
        make_donor('o_pos@example.com', 'O', '+')
        donors = eligible_compatible_donors(self._request_for('O', '-'))
        self.assertEqual([d.user.email for d in donors], ['o_neg@example.com'])

    def test_ineligible_donors_are_excluded(self):
        make_donor('recent@example.com', 'O', '-', eligible=False)
        make_donor('ready@example.com', 'O', '-')
        donors = eligible_compatible_donors(self._request_for('O', '-'))
        self.assertEqual([d.user.email for d in donors], ['ready@example.com'])

    def test_inactive_accounts_are_excluded(self):
        make_donor('inactive@example.com', 'O', '-', active=False)
        donors = eligible_compatible_donors(self._request_for('O', '-'))
        self.assertEqual(donors, [])

    def test_dispatch_sends_email_and_logs_notification(self):
        make_donor('target@example.com', 'O', '-')
        blood_request = self._request_for('A', '-')
        sent, failed = dispatch_blood_request_notifications(blood_request)

        self.assertEqual((sent, failed), (1, 0))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('A-', message.subject)
        self.assertIn('Alert Hospital', message.subject)
        self.assertEqual(message.to, ['target@example.com'])
        # HTML alternative is attached, not just plain text.
        self.assertTrue(any(mime == 'text/html' for _, mime in message.alternatives))

        note = Notification.objects.get()
        self.assertEqual(note.status, Notification.STATUS_SENT)
        self.assertEqual(note.blood_request, blood_request)

    def test_failed_send_is_logged_as_failed(self):
        make_donor('target@example.com', 'O', '-')
        blood_request = self._request_for('O', '-')
        with patch('apps.notifications.emails.EmailMultiAlternatives.send',
                   side_effect=RuntimeError('smtp down')):
            sent, failed = dispatch_blood_request_notifications(blood_request)
        self.assertEqual((sent, failed), (0, 1))
        self.assertEqual(Notification.objects.get().status, Notification.STATUS_FAILED)

    def test_insufficient_stock_hands_off_to_the_dispatcher(self):
        make_donor('helper@example.com', 'O', '-')
        self.client.force_login(self.staff)
        with patch('apps.requests.views.dispatch_blood_request_notifications_async') as dispatch:
            self.client.post(reverse('requests:create'), {
                'hospital': self.hospital.pk, 'blood_group': 'O', 'rhesus_factor': '-',
                'quantity_needed': 4, 'urgency_level': 'critical', 'notes': '',
            })
        dispatch.assert_called_once()
        blood_request = dispatch.call_args[0][0]
        self.assertEqual(blood_request.status, BloodRequest.STATUS_PENDING)
        self.assertEqual(blood_request.units_outstanding, 4)

    def test_sufficient_stock_sends_no_alerts(self):
        stock = self.hospital.inventory.get(blood_group='O', rhesus_factor='-')
        stock.available_units = 10
        stock.save()
        make_donor('helper@example.com', 'O', '-')
        self.client.force_login(self.staff)
        with patch('apps.requests.views.dispatch_blood_request_notifications_async') as dispatch:
            self.client.post(reverse('requests:create'), {
                'hospital': self.hospital.pk, 'blood_group': 'O', 'rhesus_factor': '-',
                'quantity_needed': 4, 'urgency_level': 'low', 'notes': '',
            })
        dispatch.assert_not_called()
        self.assertEqual(Notification.objects.count(), 0)


class RequestScopingTests(TestCase):
    def setUp(self):
        self.hospital_a = Hospital.objects.create(
            name='Hospital A', address='Road', city='Nsukka', state='Enugu'
        )
        self.hospital_b = Hospital.objects.create(
            name='Hospital B', address='Road', city='Nsukka', state='Enugu'
        )
        self.staff_a = User.objects.create_user(
            email='a@example.com', username='a', password='TestPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital_a,
        )
        self.staff_b = User.objects.create_user(
            email='b@example.com', username='b', password='TestPass123!',
            role=User.ROLE_STAFF, hospital=self.hospital_b,
        )
        self.request_b = BloodRequest.objects.create(
            hospital=self.hospital_b, requested_by=self.staff_b,
            blood_group='A', rhesus_factor='+', quantity_needed=2,
        )

    def test_staff_cannot_open_another_hospitals_request(self):
        self.client.force_login(self.staff_a)
        response = self.client.get(reverse('requests:detail', args=[self.request_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_admin_sees_every_request(self):
        admin = User.objects.create_superuser(
            email='admin@example.com', username='admin', password='TestPass123!'
        )
        self.client.force_login(admin)
        response = self.client.get(reverse('requests:detail', args=[self.request_b.pk]))
        self.assertEqual(response.status_code, 200)
