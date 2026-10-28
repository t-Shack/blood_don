from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def _role_required(test, message):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not test(request.user):
                messages.error(request, message)
                raise PermissionDenied(message)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


donor_required = _role_required(
    lambda user: user.is_donor,
    'That area is for registered donors only.',
)

staff_required = _role_required(
    lambda user: user.is_medical_staff or user.is_administrator,
    'That area is for medical staff only.',
)

admin_required = _role_required(
    lambda user: user.is_administrator,
    'That area is for administrators only.',
)


class RoleRequiredMixin:
    allowed_roles = ()
    permission_message = 'You do not have permission to view that page.'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_administrator or request.user.role in self.allowed_roles):
            messages.error(request, self.permission_message)
            raise PermissionDenied(self.permission_message)
        return super().dispatch(request, *args, **kwargs)


def role_home(user):
    """Where a user lands after logging in, based on their role."""
    if user.is_administrator:
        return redirect('core:admin_dashboard')
    if user.is_medical_staff:
        return redirect('requests:list')
    return redirect('accounts:dashboard')
