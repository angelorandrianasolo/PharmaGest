"""Mixins de contrôle d'accès utilisés par les vues."""

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied


class AnyPermissionRequiredMixin(AccessMixin):
    """Autorise l'accès si l'utilisateur possède au moins une des permissions."""

    permission_required = ()

    def get_permission_required(self) -> tuple[str, ...]:
        perms = self.permission_required
        if isinstance(perms, str):
            return (perms,)
        return tuple(perms)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not any(
            request.user.has_perm(perm) for perm in self.get_permission_required()
        ):
            raise PermissionDenied(
                "Vous n'avez pas l'autorisation nécessaire pour cette opération."
            )
        return super().dispatch(request, *args, **kwargs)
