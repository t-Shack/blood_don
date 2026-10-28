from django.db import models


class Notification(models.Model):
    """Log of every email dispatched to a donor, successful or not."""

    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [(STATUS_SENT, 'Sent'), (STATUS_FAILED, 'Failed')]

    donor = models.ForeignKey(
        'accounts.DonorProfile', on_delete=models.CASCADE, related_name='notifications'
    )
    blood_request = models.ForeignKey(
        'bloodrequests.BloodRequest', on_delete=models.CASCADE, related_name='notifications'
    )
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SENT)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-sent_at']
        indexes = [models.Index(fields=['status'])]

    def __str__(self):
        return f'{self.donor.user.email} - {self.get_status_display()} @ {self.sent_at:%Y-%m-%d %H:%M}'
