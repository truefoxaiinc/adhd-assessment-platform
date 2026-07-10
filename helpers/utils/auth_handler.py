from django.contrib.auth.backends import ModelBackend
from apps.users.models import Users
from django.db.models import Q


def active_not_deleted_user_authentication_rule(user):
    return bool(
        user
        and getattr(user, 'is_active', True)
        and not getattr(user, 'is_deleted', False)
    )


class UserCustomAuthenticator(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):

        try:
            user = Users.objects.filter(Q(username=username) | Q(email=username)).first()
            if (
                user is not None
                and active_not_deleted_user_authentication_rule(user)
                and user.check_password(password)
            ):
                return user
        except Exception:
            pass

        return None
