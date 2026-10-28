from django.shortcuts import render

from apps.accounts.constants import BLOOD_TYPES
from apps.hospitals.models import Hospital

from .models import BloodInventory


def inventory_overview(request):
    """Public, system-wide view: every active hospital and its eight blood types."""
    hospitals = (
        Hospital.objects.active().with_blood_bank().prefetch_related('inventory')
    )

    state = request.GET.get('state', '').strip()
    if state:
        hospitals = hospitals.filter(state__iexact=state)

    rows = []
    for hospital in hospitals:
        by_type = {
            (item.blood_group, item.rhesus_factor): item
            for item in hospital.inventory.all()
        }
        rows.append({
            'hospital': hospital,
            'cells': [by_type.get(bt) for bt in BLOOD_TYPES],
            'total_units': sum(item.available_units for item in by_type.values()),
        })

    totals = {}
    for group, rhesus in BLOOD_TYPES:
        units = sum(
            row['cells'][BLOOD_TYPES.index((group, rhesus))].available_units
            for row in rows
            if row['cells'][BLOOD_TYPES.index((group, rhesus))]
        )
        totals[f'{group}{rhesus}'] = units

    context = {
        'rows': rows,
        'blood_types': [f'{g}{r}' for g, r in BLOOD_TYPES],
        'totals': totals,
        'states': Hospital.objects.active().order_by('state')
                                  .values_list('state', flat=True).distinct(),
        'selected_state': state,
        'shortage_count': BloodInventory.objects.shortages()
                                        .filter(hospital__is_active=True).count(),
    }
    return render(request, 'inventory/overview.html', context)
