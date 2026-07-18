def user_is_manager(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name='Manager').exists()
    )
