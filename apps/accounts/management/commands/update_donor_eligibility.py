from django.core.management.base import BaseCommand

from apps.accounts.models import DonorProfile


class Command(BaseCommand):
    help = 'Recompute is_eligible for every donor against the 56-day interval.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbosity = options['verbosity']
        became_eligible = became_ineligible = 0

        for profile in DonorProfile.objects.select_related('user').iterator():
            was_eligible = profile.is_eligible
            if dry_run:
                from datetime import date

                from django.conf import settings
                if profile.last_donation_date:
                    now_eligible = (
                        (date.today() - profile.last_donation_date).days
                        >= settings.DONATION_INTERVAL_DAYS
                    )
                else:
                    now_eligible = True
            else:
                now_eligible = profile.update_eligibility()

            if now_eligible and not was_eligible:
                became_eligible += 1
                if verbosity >= 2:
                    self.stdout.write(f'  eligible again: {profile.user.email}')
            elif was_eligible and not now_eligible:
                became_ineligible += 1
                if verbosity >= 2:
                    self.stdout.write(f'  now deferred:   {profile.user.email}')

        if verbosity >= 1:
            prefix = '[dry run] ' if dry_run else ''
            self.stdout.write(self.style.SUCCESS(
                f'{prefix}{became_eligible} donor(s) became eligible, '
                f'{became_ineligible} became ineligible.'
            ))
