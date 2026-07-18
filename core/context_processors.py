from .permissions import user_is_manager


def role_flags(request):
    return {'is_manager': user_is_manager(request.user)}
