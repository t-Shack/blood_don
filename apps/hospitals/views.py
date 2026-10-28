from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from apps.inventory.models import BloodInventory

from .models import Hospital


def hospital_list(request):
    """Public directory of active hospitals, filterable by city and state."""
    hospitals = Hospital.objects.active().prefetch_related('inventory')

    city = request.GET.get('city', '').strip()
    state = request.GET.get('state', '').strip()
    query = request.GET.get('q', '').strip()
    blood_bank_only = request.GET.get('blood_bank') == '1'

    if city:
        hospitals = hospitals.filter(city__iexact=city)
    if state:
        hospitals = hospitals.filter(state__iexact=state)
    if query:
        hospitals = hospitals.filter(name__icontains=query)
    if blood_bank_only:
        hospitals = hospitals.with_blood_bank()

    context = {
        'hospitals': hospitals,
        'cities': Hospital.objects.active().order_by('city')
                                  .values_list('city', flat=True).distinct(),
        'states': Hospital.objects.active().order_by('state')
                                  .values_list('state', flat=True).distinct(),
        'selected_city': city,
        'selected_state': state,
        'query': query,
        'blood_bank_only': blood_bank_only,
    }
    return render(request, 'hospitals/list.html', context)


def hospital_detail(request, pk):
    hospital = get_object_or_404(
        Hospital.objects.prefetch_related(
            Prefetch('inventory', queryset=BloodInventory.objects.ordered())
        ),
        pk=pk,
        is_active=True,
    )
    inventory = list(hospital.inventory.all())
    context = {
        'hospital': hospital,
        'inventory': inventory,
        'shortage_count': sum(1 for item in inventory if item.is_in_shortage),
    }
    return render(request, 'hospitals/detail.html', context)


def hospital_inventory(request, pk):
    """Per-hospital live inventory page; refreshed by AJAX polling."""
    hospital = get_object_or_404(Hospital, pk=pk, is_active=True)
    inventory = BloodInventory.objects.for_hospital(hospital)
    return render(request, 'hospitals/inventory.html', {
        'hospital': hospital,
        'inventory': inventory,
    })
