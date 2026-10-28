from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from apps.accounts.decorators import staff_required

from .forms import DonationRecordForm
from .models import DonationRecord


@staff_required
def donation_record(request):
    if request.method == 'POST':
        form = DonationRecordForm(request.POST, user=request.user)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.recorded_by = request.user
            if form.fields['hospital'].disabled and request.user.hospital_id:
                donation.hospital_id = request.user.hospital_id
            donation.save()
            messages.success(
                request,
                f'Recorded {donation.units_donated} unit(s) of {donation.blood_type} '
                f'from {donation.donor.user.get_full_name()}. Stock updated.',
            )
            return redirect('donations:list')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = DonationRecordForm(user=request.user)
    return render(request, 'donations/record.html', {'form': form})


@login_required
def donation_list(request):
    """Donors see their own history; staff their hospital's; admins everything."""
    queryset = (
        DonationRecord.objects.for_user(request.user)
        .select_related('donor__user', 'hospital', 'recorded_by')
    )
    page = Paginator(queryset, 25).get_page(request.GET.get('page'))
    context = {
        'page_obj': page,
        'donations': page.object_list,
        'total_units': sum(d.units_donated for d in queryset),
        'total_records': queryset.count(),
    }
    return render(request, 'donations/list.html', context)
