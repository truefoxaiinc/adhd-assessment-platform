from apps.users.models import Users
from django.db import transaction


class RegistrationService:
    @staticmethod
    def ensure_initial_goal(user):
        from apps.progresstracker.models import UserGoal

        UserGoal.objects.get_or_create(
            user=user,
            is_first=True,
            defaults={
                'goal': '',
                'rating': 0,
                'is_last': False,
            },
        )

    @staticmethod
    @transaction.atomic
    def create_user(username, email, password):
        user = Users(username=username, email=email)
        user.set_password(password)
        user.is_admin = False
        user.is_staff = False
        user.is_superuser = False
        user.save()
        RegistrationService.ensure_initial_goal(user)
        return user
