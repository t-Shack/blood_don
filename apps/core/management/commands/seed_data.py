import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.constants import BLOOD_TYPES
from apps.accounts.models import DonorProfile, User
from apps.core.models import DonationCriteria
from apps.hospitals.models import Hospital
from apps.inventory.models import BloodInventory

NSUKKA_HOSPITALS = [
    {
        'name': 'University of Nigeria Teaching Hospital Annex, Nsukka',
        'address': 'UNN Campus Road, University of Nigeria',
        'city': 'Nsukka', 'state': 'Enugu',
        'phone_number': '08031234501',
        'email': 'bloodbank@unthannex.ng',
        'has_blood_bank': True, 'blood_bank_capacity': 320,
    },
    {
        'name': 'Bishop Shanahan Hospital',
        'address': 'Ogurugu Road, Nsukka',
        'city': 'Nsukka', 'state': 'Enugu',
        'phone_number': '08031234502',
        'email': 'info@bishopshanahan.ng',
        'has_blood_bank': True, 'blood_bank_capacity': 200,
    },
    {
        'name': 'Nsukka General Hospital',
        'address': 'Enugu Road, Nsukka',
        'city': 'Nsukka', 'state': 'Enugu',
        'phone_number': '08031234503',
        'email': 'contact@nsukkageneral.ng',
        'has_blood_bank': True, 'blood_bank_capacity': 180,
    },
    {
        'name': 'University of Nigeria Medical Centre',
        'address': 'University of Nigeria, Nsukka Campus',
        'city': 'Nsukka', 'state': 'Enugu',
        'phone_number': '08031234504',
        'email': 'medicalcentre@unn.edu.ng',
        'has_blood_bank': True, 'blood_bank_capacity': 150,
    },
    {
        'name': 'Mount Carmel Specialist Hospital',
        'address': 'Odenigbo Road, Nsukka',
        'city': 'Nsukka', 'state': 'Enugu',
        'phone_number': '08031234505',
        'email': 'care@mountcarmelnsukka.ng',
        'has_blood_bank': True, 'blood_bank_capacity': 120,
    },
    {
        'name': 'Divine Mercy Hospital, Nsukka',
        'address': 'Onuiyi Haven, Nsukka',
        'city': 'Nsukka', 'state': 'Enugu',
        'phone_number': '08031234506',
        'email': 'admin@divinemercynsukka.ng',
        'has_blood_bank': True, 'blood_bank_capacity': 90,
    },
    {
        'name': 'Ejike Memorial Hospital',
        'address': 'Obukpa Road, Nsukka',
        'city': 'Nsukka', 'state': 'Enugu',
        'phone_number': '08031234507',
        'email': 'ejikememorial@health.ng',
        'has_blood_bank': False, 'blood_bank_capacity': 0,
    },
]

CRITERIA = [
    {
        'title': 'Age and weight',
        'icon': '🎂',
        'order': 1,
        'content': (
            'You must be between 18 and 65 years old.\n'
            'You must weigh at least 50kg (110lbs).\n'
            'First-time donors above 60 may be asked for a physician’s clearance.'
        ),
    },
    {
        'title': 'Health on the day',
        'icon': '🩺',
        'order': 2,
        'content': (
            'Haemoglobin of at least 12.5g/dL for women and 13.0g/dL for men.\n'
            'Blood pressure between 90/60 and 160/100 mmHg.\n'
            'Body temperature not above 37.5°C.\n'
            'You should feel well, have eaten within four hours, and be well hydrated.'
        ),
    },
    {
        'title': 'How often you can donate',
        'icon': '📅',
        'order': 3,
        'content': (
            'A minimum of 56 days (8 weeks) must pass between whole-blood donations.\n'
            'This system tracks the interval for you and shows your next eligible date.\n'
            'A maximum of four donations per year is recommended for women, five for men.'
        ),
    },
    {
        'title': 'Conditions that disqualify donation',
        'icon': '⛔',
        'order': 4,
        'content': (
            'HIV, hepatitis B or C, or any other transfusion-transmissible infection.\n'
            'Active tuberculosis, or an untreated sexually transmitted infection.\n'
            'Uncontrolled hypertension, heart disease, or a bleeding disorder.\n'
            'Cancer under active treatment.\n'
            'Pregnancy, or within six months of childbirth or termination.\n'
            'Sickle cell disease (carriers with trait may donate after screening).'
        ),
    },
    {
        'title': 'Temporary deferrals',
        'icon': '⏳',
        'order': 5,
        'content': (
            'Malaria: defer for 3 months after full recovery.\n'
            'Any fever or infection: defer until 14 days after symptoms end.\n'
            'Tattoo, piercing or scarification: defer for 6 months.\n'
            'Major surgery: defer for 6 months; minor surgery for 1 month.\n'
            'Blood transfusion received: defer for 12 months.\n'
            'Vaccination: defer for 14 to 28 days depending on the vaccine.'
        ),
    },
    {
        'title': 'Medication restrictions',
        'icon': '💊',
        'order': 6,
        'content': (
            'Antibiotics: wait until the course is complete plus 7 days.\n'
            'Aspirin or anti-platelet drugs: wait 3 days (plasma donation only).\n'
            'Anticoagulants such as warfarin: you cannot donate while taking them.\n'
            'Isotretinoin and finasteride: wait 1 month after the last dose.\n'
            'Routine medication for blood pressure, contraception, or allergies does not '
            'disqualify you.'
        ),
    },
    {
        'title': 'After you donate',
        'icon': '🧃',
        'order': 7,
        'content': (
            'Rest for 10 to 15 minutes and take the refreshment offered.\n'
            'Drink extra fluids for the next 24 hours.\n'
            'Avoid heavy lifting or strenuous exercise for the rest of the day.\n'
            'Keep the dressing on for at least four hours.\n'
            'If you feel faint, lie down and raise your legs, then tell the staff.'
        ),
    },
]


class Command(BaseCommand):
    help = 'Seed hospitals, blood inventory rows and donation criteria content.'

    def _say(self, message):
        if getattr(self, 'verbosity', 1) >= 1:
            self.stdout.write(message)

    def add_arguments(self, parser):
        parser.add_argument(
            '--demo', action='store_true',
            help='Also create demo donors, staff accounts and randomised stock levels.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        hospitals = self._seed_hospitals()
        self._seed_criteria()
        if options['demo']:
            self._seed_demo(hospitals)
        self._say(self.style.SUCCESS('Seeding complete.'))

    def _seed_hospitals(self):
        hospitals = []
        for data in NSUKKA_HOSPITALS:
            hospital, created = Hospital.objects.update_or_create(
                name=data['name'], city=data['city'], defaults=data,
            )
            if hospital.has_blood_bank:
                BloodInventory.objects.ensure_for_hospital(hospital)
            hospitals.append(hospital)
            verb = 'Created' if created else 'Updated'
            self._say(f'  {verb} hospital: {hospital.name}')
        return hospitals

    def _seed_criteria(self):
        for data in CRITERIA:
            DonationCriteria.objects.update_or_create(
                title=data['title'], defaults=data,
            )
        self._say(f'  {len(CRITERIA)} criteria sections in place.')

    def _seed_demo(self, hospitals):
        rng = random.Random(42)
        banked = [h for h in hospitals if h.has_blood_bank]

        for hospital in banked:
            for item in BloodInventory.objects.for_hospital(hospital):
                item.available_units = rng.choice([0, 2, 3, 6, 9, 14, 21, 28])
                item.critical_threshold = 5
                item.save(update_fields=['available_units', 'critical_threshold'])

        admin, created = User.objects.get_or_create(
            email='admin@bdmis.ng',
            defaults={'username': 'bdmis_admin', 'full_name': 'System Administrator',
                      'role': User.ROLE_ADMIN, 'is_staff': True, 'is_superuser': True},
        )
        if created:
            admin.set_password('BdmisAdmin2025')
            admin.save()
        self._say('  Demo admin: admin@bdmis.ng / BdmisAdmin2025')

        for index, hospital in enumerate(banked[:3], start=1):
            staff, staff_created = User.objects.get_or_create(
                email=f'staff{index}@bdmis.ng',
                defaults={'username': f'staff{index}', 'full_name': f'Medical Staff {index}',
                          'role': User.ROLE_STAFF, 'hospital': hospital},
            )
            if staff_created:
                staff.set_password('BdmisStaff2025')
                staff.save()
        self._say('  Demo staff: staff1@bdmis.ng … / BdmisStaff2025')

        first_names = ['Chidinma', 'Emeka', 'Ngozi', 'Ifeanyi', 'Adaeze', 'Obinna',
                       'Chiamaka', 'Uche', 'Nnamdi', 'Amaka', 'Kelechi', 'Ifeoma',
                       'Chukwudi', 'Oluchi', 'Ekene', 'Nkiru']
        last_names = ['Okeke', 'Eze', 'Nwosu', 'Okafor', 'Ugwu', 'Attah', 'Onyeka', 'Asogwa']

        for index in range(1, 25):
            email = f'donor{index}@example.com'
            group, rhesus = BLOOD_TYPES[index % len(BLOOD_TYPES)]
            name = f'{rng.choice(first_names)} {rng.choice(last_names)}'
            user, user_created = User.objects.get_or_create(
                email=email,
                defaults={'username': f'donor{index}', 'full_name': name,
                          'role': User.ROLE_DONOR},
            )
            if user_created:
                user.set_password('BdmisDonor2025')
                user.save()
            profile = DonorProfile.objects.get(user=user)
            profile.blood_group = group
            profile.rhesus_factor = rhesus
            profile.date_of_birth = date(rng.randint(1975, 2004), rng.randint(1, 12), 15)
            profile.phone_number = f'0803{rng.randint(1000000, 9999999)}'
            profile.city, profile.state = 'Nsukka', 'Enugu'
            # A third of the donors are inside their 56-day window.
            if index % 3 == 0:
                profile.last_donation_date = date.today() - timedelta(days=rng.randint(5, 50))
            else:
                profile.last_donation_date = None
            profile.save()
            profile.update_eligibility()

        self._say('  24 demo donors: donor1@example.com … / BdmisDonor2025')
