from apps.users.models import Users
from django.db import transaction


class RegistrationService:
    @staticmethod
    @transaction.atomic
    def create_user(username, email, password):
        user = Users(username=username, email=email)
        user.set_password(password)
        user.is_admin = False
        user.is_staff = False
        user.is_superuser = False
        user.save()
        return user
