from rest_framework import permissions

class IsSupplier(permissions.BasePermission):
    """Разрешение только для поставщиков"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'supplier'


class IsClient(permissions.BasePermission):
    """Разрешение только для клиентов"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'client'