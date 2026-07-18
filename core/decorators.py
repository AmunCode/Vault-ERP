from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .permissions import user_is_manager


def manager_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if user_is_manager(request.user):
            return view_func(request, *args, **kwargs)
        messages.error(request, "You don't have permission to access that page.")
        return redirect('dashboard')
    return wrapper
