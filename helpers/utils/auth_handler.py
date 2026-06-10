from django.contrib.auth.backends import ModelBackend
from apps.users.models import Users
from django.db.models import Q

class UserCustomAuthenticator(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):

        try:
            user = Users.objects.filter(Q(username=username) | Q(email=username)).first()
            if user is not None and user.check_password(password):
                return user
        except:
            pass

        return None