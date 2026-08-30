from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsStaffOrReadOnly(BasePermission):
    """
    Anyone may read the catalog; only staff may modify it.

    Editing products is a shop-owner action, so being a registered customer is
    not enough -- that would let any signed-up visitor delete the menu.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        
        return bool(request.user and request.user.is_staff)
