from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import admin_required
from apps.accounts.forms import StaffUserForm
from apps.accounts.models import DonorProfile, User
from apps.donations.models import DonationRecord
from apps.hospitals.forms import HospitalForm
from apps.hospitals.models import Hospital
from apps.inventory.forms import BloodInventoryFormSet
from apps.inventory.models import BloodInventory
from apps.notifications.models import Notification
from apps.requests.models import BloodRequest

from .forms import DonationCriteriaForm
from .models import DonationCriteria


@admin_required
def dashboard(request):
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    shortages = (
        BloodInventory.objects.shortages()
        .filter(hospital__is_active=True)
        .select_related('hospital')
        .ordered()
    )
    context = {
        'hospital_count': Hospital.objects.active().count(),
        'donor_count': DonorProfile.objects.filter(user__is_active=True).count(),
        'eligible_donor_count': DonorProfile.objects.filter(
            user__is_active=True, is_eligible=True).count(),
        'staff_count': User.objects.filter(role=User.ROLE_STAFF, is_active=True).count(),
        'total_units': BloodInventory.objects.filter(hospital__is_active=True)
                                     .aggregate(total=Sum('available_units'))['total'] or 0,
        'pending_requests': BloodRequest.objects.pending().count(),
        'critical_requests': BloodRequest.objects.pending().filter(
            urgency_level=BloodRequest.URGENCY_CRITICAL).count(),
        'recent_donations': DonationRecord.objects.filter(donation_date__gte=thirty_days_ago)
                                          .aggregate(total=Sum('units_donated'))['total'] or 0,
        'shortages': shortages[:12],
        'shortage_count': shortages.count(),
        'latest_requests': BloodRequest.objects.select_related(
            'hospital', 'requested_by')[:8],
        'latest_donations': DonationRecord.objects.select_related(
            'donor__user', 'hospital')[:8],
        'failed_notifications': Notification.objects.filter(
            status=Notification.STATUS_FAILED).count(),
    }
    return render(request, 'admin_panel/dashboard.html', context)


# --- Hospitals ------------------------------------------------------------

@admin_required
def hospital_list(request):
    query = request.GET.get('q', '').strip()
    hospitals = Hospital.objects.annotate(
        stock=Sum('inventory__available_units'),
        critical_count=Count('inventory', filter=Q(
            inventory__available_units__lt=F('inventory__critical_threshold'))),
    )
    if query:
        hospitals = hospitals.filter(
            Q(name__icontains=query) | Q(city__icontains=query) | Q(state__icontains=query)
        )
    page = Paginator(hospitals, 20).get_page(request.GET.get('page'))
    return render(request, 'admin_panel/hospital_list.html', {
        'page_obj': page, 'hospitals': page.object_list, 'query': query,
    })


@admin_required
def hospital_add(request):
    if request.method == 'POST':
        form = HospitalForm(request.POST)
        if form.is_valid():
            hospital = form.save()
            # The post_save signal seeds the eight inventory rows.
            messages.success(request, f'{hospital.name} added to the directory.')
            return redirect('core:admin_hospitals')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = HospitalForm()
    return render(request, 'admin_panel/hospital_form.html', {'form': form, 'is_add': True})


@admin_required
def hospital_edit(request, pk):
    hospital = get_object_or_404(Hospital, pk=pk)
    if request.method == 'POST':
        form = HospitalForm(request.POST, instance=hospital)
        if form.is_valid():
            form.save()
            if hospital.has_blood_bank:
                BloodInventory.objects.ensure_for_hospital(hospital)
            messages.success(request, f'{hospital.name} updated.')
            return redirect('core:admin_hospitals')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = HospitalForm(instance=hospital)
    return render(request, 'admin_panel/hospital_form.html', {
        'form': form, 'hospital': hospital, 'is_add': False,
    })


@admin_required
def hospital_toggle(request, pk):
    """Deactivate or reactivate a hospital — rows are never deleted."""
    hospital = get_object_or_404(Hospital, pk=pk)
    if request.method == 'POST':
        hospital.is_active = not hospital.is_active
        hospital.save(update_fields=['is_active', 'updated_at'])
        state = 'reactivated' if hospital.is_active else 'deactivated'
        messages.info(request, f'{hospital.name} {state}.')
    return redirect('core:admin_hospitals')


@admin_required
def hospital_inventory_edit(request, pk):
    """Bulk-edit one hospital's eight stock rows."""
    hospital = get_object_or_404(Hospital, pk=pk)
    BloodInventory.objects.ensure_for_hospital(hospital)
    queryset = BloodInventory.objects.for_hospital(hospital)

    if request.method == 'POST':
        formset = BloodInventoryFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            formset.save()
            messages.success(request, f'Inventory updated for {hospital.name}.')
            return redirect('core:admin_hospital_inventory', pk=hospital.pk)
        messages.error(request, 'Please correct the highlighted values.')
    else:
        formset = BloodInventoryFormSet(queryset=queryset)

    return render(request, 'admin_panel/inventory_form.html', {
        'hospital': hospital,
        'formset': formset,
        'rows': zip(formset.forms, queryset),
    })


# --- Users ----------------------------------------------------------------

@admin_required
def user_list(request):
    role = request.GET.get('role', '').strip()
    query = request.GET.get('q', '').strip()
    users = User.objects.select_related('hospital', 'donor_profile')
    if role:
        users = users.filter(role=role)
    if query:
        users = users.filter(
            Q(email__icontains=query) | Q(username__icontains=query)
            | Q(full_name__icontains=query)
        )
    page = Paginator(users, 25).get_page(request.GET.get('page'))
    return render(request, 'admin_panel/user_list.html', {
        'page_obj': page,
        'users': page.object_list,
        'role_choices': User.ROLE_CHOICES,
        'selected_role': role,
        'query': query,
    })


@admin_required
def user_add(request):
    if request.method == 'POST':
        form = StaffUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Account created for {user.get_full_name()}.')
            return redirect('core:admin_users')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = StaffUserForm()
    return render(request, 'admin_panel/user_form.html', {'form': form, 'is_add': True})


@admin_required
def user_edit(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = StaffUserForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'{user_obj.get_full_name()} updated.')
            return redirect('core:admin_users')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = StaffUserForm(instance=user_obj)
    return render(request, 'admin_panel/user_form.html', {
        'form': form, 'user_obj': user_obj, 'is_add': False,
    })


@admin_required
def user_toggle(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        if user_obj.pk == request.user.pk:
            messages.error(request, 'You cannot deactivate your own account.')
        else:
            user_obj.is_active = not user_obj.is_active
            user_obj.save(update_fields=['is_active'])
            state = 'reactivated' if user_obj.is_active else 'deactivated'
            messages.info(request, f'{user_obj.get_full_name()} {state}.')
    return redirect('core:admin_users')


# --- Requests, donations, criteria, notifications -------------------------

@admin_required
def request_overview(request):
    queryset = BloodRequest.objects.select_related('hospital', 'requested_by')
    status = request.GET.get('status', '').strip()
    if status:
        queryset = queryset.filter(status=status)
    page = Paginator(queryset, 25).get_page(request.GET.get('page'))
    return render(request, 'admin_panel/request_list.html', {
        'page_obj': page,
        'requests': page.object_list,
        'status_choices': BloodRequest.STATUS_CHOICES,
        'selected_status': status,
    })


@admin_required
def criteria_list(request):
    return render(request, 'admin_panel/criteria_list.html', {
        'criteria_list': DonationCriteria.objects.all(),
    })


@admin_required
def criteria_add(request):
    if request.method == 'POST':
        form = DonationCriteriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Criteria section added.')
            return redirect('core:admin_criteria')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = DonationCriteriaForm()
    return render(request, 'admin_panel/criteria_form.html', {'form': form, 'is_add': True})


@admin_required
def criteria_edit(request, pk):
    item = get_object_or_404(DonationCriteria, pk=pk)
    if request.method == 'POST':
        form = DonationCriteriaForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Criteria section updated.')
            return redirect('core:admin_criteria')
        messages.error(request, 'Please correct the highlighted fields.')
    else:
        form = DonationCriteriaForm(instance=item)
    return render(request, 'admin_panel/criteria_form.html', {
        'form': form, 'item': item, 'is_add': False,
    })


@admin_required
def criteria_delete(request, pk):
    item = get_object_or_404(DonationCriteria, pk=pk)
    if request.method == 'POST':
        title = item.title
        item.delete()
        messages.info(request, f'"{title}" removed.')
    return redirect('core:admin_criteria')


@admin_required
def notification_log(request):
    queryset = Notification.objects.select_related(
        'donor__user', 'blood_request__hospital'
    )
    status = request.GET.get('status', '').strip()
    if status:
        queryset = queryset.filter(status=status)
    page = Paginator(queryset, 40).get_page(request.GET.get('page'))
    return render(request, 'admin_panel/notification_list.html', {
        'page_obj': page,
        'notifications': page.object_list,
        'sent_count': Notification.objects.filter(status=Notification.STATUS_SENT).count(),
        'failed_count': Notification.objects.filter(status=Notification.STATUS_FAILED).count(),
        'selected_status': status,
    })
