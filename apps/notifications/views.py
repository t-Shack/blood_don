from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from .models import Notification


@login_required
def notification_list(request):
    """A donor's own alert history. Opening the page marks them read."""
    if not request.user.is_donor:
        return redirect('core:admin_notifications')

    profile = request.user.donor_profile
    queryset = profile.notifications.select_related('blood_request__hospital')
    page = Paginator(queryset, 25).get_page(request.GET.get('page'))
    unread = queryset.filter(is_read=False)
    unread_count = unread.count()
    if unread_count:
        unread.update(is_read=True)

    return render(request, 'notifications/list.html', {
        'page_obj': page,
        'notifications': page.object_list,
        'marked_read': unread_count,
    })
