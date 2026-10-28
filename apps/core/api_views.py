from django.db.models import Sum
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.hospitals.models import Hospital
from apps.inventory.models import BloodInventory
from apps.requests.models import BloodRequest


def envelope(data=None, message='', success=True, http_status=status.HTTP_200_OK):
    return Response(
        {'success': success, 'data': data, 'message': message}, status=http_status
    )


@api_view(['GET'])
def hospital_inventory(request, hospital_id):
    """Live inventory for one hospital. Public — polled every 30s by the UI."""
    try:
        hospital = Hospital.objects.get(pk=hospital_id, is_active=True)
    except Hospital.DoesNotExist:
        return envelope(
            message='Hospital not found.', success=False,
            http_status=status.HTTP_404_NOT_FOUND,
        )

    items = BloodInventory.objects.for_hospital(hospital)
    return envelope(
        data={
            'hospital': {'id': hospital.pk, 'name': hospital.name, 'city': hospital.city},
            'inventory': [item.as_dict() for item in items],
            'total_units': sum(item.available_units for item in items),
        },
        message='Inventory retrieved.',
    )


@api_view(['GET'])
def inventory_overview(request):
    """Every active hospital's stock in one payload, for the overview page."""
    hospitals = Hospital.objects.active().with_blood_bank().prefetch_related('inventory')
    payload = [
        {
            'hospital_id': hospital.pk,
            'hospital_name': hospital.name,
            'city': hospital.city,
            'inventory': [
                item.as_dict() for item in BloodInventory.objects.for_hospital(hospital)
            ],
        }
        for hospital in hospitals
    ]
    return envelope(data={'hospitals': payload}, message='Overview retrieved.')


@api_view(['GET'])
def hospitals_in_shortage(request):
    """Hospitals with at least one blood type below its critical threshold."""
    shortages = (
        BloodInventory.objects.shortages()
        .filter(hospital__is_active=True)
        .select_related('hospital')
        .ordered()
    )
    grouped = {}
    for item in shortages:
        entry = grouped.setdefault(item.hospital_id, {
            'hospital_id': item.hospital_id,
            'hospital_name': item.hospital.name,
            'city': item.hospital.city,
            'state': item.hospital.state,
            'shortage_types': [],
        })
        entry['shortage_types'].append(item.full_blood_type)

    return envelope(
        data={
            'hospitals': list(grouped.values()),
            # Hospitals with at least one blood type below threshold.
            'count': len(grouped),
            # (hospital, blood type) rows below threshold: the figure the landing
            # page badge renders, so the server and the poll always agree.
            'type_count': sum(len(entry['shortage_types']) for entry in grouped.values()),
        },
        message='Shortages retrieved.',
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def donor_eligibility(request):
    """The signed-in donor's own eligibility state."""
    if not request.user.is_donor:
        return envelope(
            message='Only donor accounts have an eligibility record.',
            success=False, http_status=status.HTTP_403_FORBIDDEN,
        )

    profile = request.user.donor_profile
    profile.update_eligibility()
    next_date = profile.next_eligible_date
    return envelope(data={
        'blood_type': profile.full_blood_type,
        'is_eligible': profile.is_eligible,
        'last_donation_date': profile.last_donation_date.isoformat()
        if profile.last_donation_date else None,
        'next_eligible_date': next_date.isoformat() if next_date else None,
        'days_until_eligible': profile.days_until_eligible,
        'total_units_donated': profile.donations.aggregate(
            total=Sum('units_donated'))['total'] or 0,
    }, message='Eligibility retrieved.')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fulfil_request(request, pk):
    """Release units from stock against a pending request (staff/admin only)."""
    if not (request.user.is_medical_staff or request.user.is_administrator):
        return envelope(
            message='Only medical staff can fulfil requests.',
            success=False, http_status=status.HTTP_403_FORBIDDEN,
        )

    blood_request = BloodRequest.objects.for_user(request.user).filter(pk=pk).first()
    if blood_request is None:
        return envelope(
            message='Request not found.', success=False,
            http_status=status.HTTP_404_NOT_FOUND,
        )
    if not blood_request.is_open:
        return envelope(
            message='That request is no longer open.', success=False,
            http_status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        units = int(request.data.get('units_fulfilled', blood_request.units_outstanding))
    except (TypeError, ValueError):
        return envelope(
            message='units_fulfilled must be a whole number.', success=False,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    if units < 1:
        return envelope(
            message='Release at least one unit.', success=False,
            http_status=status.HTTP_400_BAD_REQUEST,
        )

    taken = blood_request.try_fulfil_from_stock(units)
    if not taken:
        return envelope(
            message='No matching units are available at this hospital.',
            success=False, http_status=status.HTTP_400_BAD_REQUEST,
        )

    inventory = blood_request.matching_inventory()
    return envelope(data={
        'request_id': blood_request.pk,
        'status': blood_request.status,
        'units_fulfilled': blood_request.units_fulfilled,
        'units_outstanding': blood_request.units_outstanding,
        'updated_inventory': inventory.as_dict() if inventory else None,
    }, message=f'{taken} unit(s) released from stock.')
