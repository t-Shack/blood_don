from django.db import models


class DonationCriteria(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField(help_text='One point per line. Rendered as a list.')
    icon = models.CharField(
        max_length=8, blank=True, default='',
        help_text='Optional emoji shown beside the heading.',
    )
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        verbose_name_plural = 'donation criteria'

    def __str__(self):
        return self.title

    @property
    def points(self):
        """Content split into lines for list rendering; escaped by the template."""
        return [line.strip() for line in self.content.splitlines() if line.strip()]


class SiteStatistic(models.Model):
    key = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=100)
    value = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f'{self.label}: {self.value}'
