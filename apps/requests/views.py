import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import staff_required
from apps.notifications.dispatch import dispatch_blood_request_notifications_async

from .forms import BloodRequestForm, FulfilRequestForm
from .models import BloodRequest

logger = logging.getLogger(__name__)


@staff_required
def request_list(request):
    """Staff see their hospital's requests; admins see every request."""
    queryset = (
        BloodRequest.objects.for_user(request.user)
        .select_related('hospital', 'requested_by')
    )

    status = request.GET.get('status', '').strip()
    urgency = request.GET.get('urgency', '').strip()
    if status:
        queryset = queryset.filter(status=status)
    if urgency:
        queryset = queryset.filter(urgency_level=urgency)

    page = Paginator(queryset, 20).get_page(request.GET.get('page'))
    context = {
        'page_obj': page,
        'requests': page.object_list,
        'status_choices': BloodRequest.STATUS_CHOICES,
        'urgency_choices': BloodRequest.URGENCY_CHOICES,
        'selected_status': status,
        'selected_urgency': urgency,
        'pending_count': BloodRequest.objects.for_user(request.user).pending().count(),
    }
    return render(request, 'requests/list.html', context)


@staff_required
def request_create(request):
    """Submit a request, drawing from stock first and alerting donors otherwise."""
    if request.method == 'POST':
        form = BloodRequestForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                blood_request = form.save(commit=False)
                blood_request.requested_by = request.user
                if form.fields['hospital'].disabled and request.user.hospital_id:
                    blood_request.hospital_id = request.user.hospital_id
                blood_request.save()
                taken = blood_request.try_fulfil_from_stock()

            if blood_request.status == BloodRequest.STATUS_FULFILLED:
                messages.success(
                    request,
                    f'Request fulfilled immediately from stock ({taken} '
                    f'{"unit" if taken == 1 else "units"} released).',
                )
            else:
                outstanding = blood_request.units_outstanding
                dispatch_blood_request_notifications_async(blood_request)
                messages.warning(
                    request,
                    f'Only {taken} of {blood_request.quantity_needed} units were in stock. '
                    f'{outstanding} still outstanding, so compatible donors are being alerted by email.',
                )
            return redirect('requests:detail', pk=blood_request.pk)
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = BloodRequestForm(user=request.user)

    return render(request, 'requests/create.html', {'form': form})


@staff_required
def request_detail(request, pk):
    blood_request = get_object_or_404(
        BloodRequest.objects.for_user(request.user).select_related(
            'hospital', 'requested_by'
        ),
        pk=pk,
    )
    inventory = blood_request.matching_inventory()
    context = {
        'blood_request': blood_request,
        'inventory': inventory,
        'compatible_types': [
            f'{g}{r}' for g, r in blood_request.get_compatible_blood_groups()
        ],
        'notifications': blood_request.notifications.select_related('donor__user')[:50],
        'donations': blood_request.donations.select_related('donor__user'),
        'fulfil_form': FulfilRequestForm(blood_request=blood_request),
    }
    return render(request, 'requests/detail.html', context)


@staff_required
def request_fulfil(request, pk):
    """Release units from stock against a pending request."""
    blood_request = get_object_or_404(BloodRequest.objects.for_user(request.user), pk=pk)
    if request.method != 'POST':
        return redirect('requests:detail', pk=pk)

    if not blood_request.is_open:
        messages.error(request, 'That request is no longer open.')
        return redirect('requests:detail', pk=pk)

    form = FulfilRequestForm(request.POST, blood_request=blood_request)
    if form.is_valid():
        taken = blood_request.try_fulfil_from_stock(form.cleaned_data['units_fulfilled'])
        if taken:
            messages.success(request, f'{taken} unit(s) released from stock.')
        else:
            messages.error(request, 'No matching units are available at this hospital.')
    else:
        messages.error(request, 'Enter a valid number of units.')
    return redirect('requests:detail', pk=pk)


@staff_required
def request_cancel(request, pk):
    blood_request = get_object_or_404(BloodRequest.objects.for_user(request.user), pk=pk)
    if request.method != 'POST':
        return redirect('requests:detail', pk=pk)
    if not blood_request.is_open:
        messages.error(request, 'Only pending requests can be cancelled.')
    else:
        blood_request.cancel()
        messages.info(request, 'Request cancelled.')
    return redirect('requests:detail', pk=pk)
