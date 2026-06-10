from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import datetime, timedelta


class GenderCategory(models.TextChoices):
    MALE    = 'MALE', _('Male')
    FEMALE  = 'FEMALE', _('Female')
    OTHER   = 'OTHER', _('Other')


class UserManager(BaseUserManager):
    def create_user(self, username, password = None, **extra_fields):
        if not username:
            raise ValueError(_('The Email must be set'))

        username = self.normalize_email(username)
        user = self.model(username = username, **extra_fields)
        if password:

            user.set_password(password.strip())
        user.save()
        return user

    def create_superuser(self, username, password, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('is_staff', True)
        return self.create_user(username, password, **extra_fields)


class Users(AbstractBaseUser, PermissionsMixin):
    email                 = models.EmailField(_('email'), unique = True, max_length = 255, blank = True, null = True)
    username              = models.CharField(_('username'), max_length = 300, unique = True, blank = True, null = True)
    password              = models.CharField(_('password'), max_length=255, blank = True, null = True)
    dob                   = models.DateField(_('DOB'),  auto_now_add = False, blank = True, null = True)
    gender                = models.CharField(_('Gender'),max_length=50,choices=GenderCategory.choices,default=GenderCategory.MALE)
    country               = models.CharField(_('Country'), max_length=255, blank = True, null = True)
    height                = models.CharField(_('Height'), max_length=255, blank = True, null = True)
    weight                = models.CharField(_('Weight'), max_length=255, blank = True, null = True)
    profile_image         = models.ImageField(_('Profile Image'), upload_to='profile_images/', blank=True, null=True)
    is_verified           = models.BooleanField(default = False)
    is_admin              = models.BooleanField(default = False)
    is_staff              = models.BooleanField(default = True)
    is_superuser          = models.BooleanField(default = False)
    is_deleted            = models.BooleanField(default = False)
    ai_assessment_score   = models.FloatField(_('AI Assessment Score'), blank=True, null=True)

    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    class Meta:
        verbose_name          = _("Users")
        verbose_name_plural   = _("Users")
        db_table              = 'Users'

    def __str__(self):
        return self.username or ''

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        return True
    
    @property
    def adult(self):
        if not self.dob:
            return None
        today = timezone.now().date()
        age = today.year - self.dob.year
        if (today.month, today.day) < (self.dob.month, self.dob.day):
            age -= 1
        
        if age > 18 :
            return True
        return False
    
    @property
    def age_category(self):
        if not self.dob:
            return None
        today = timezone.now().date()
        age = today.year - self.dob.year
        if (today.month, today.day) < (self.dob.month, self.dob.day):
            age -= 1

        if age < 11:
            return 'child'
        elif 11 <= age < 16:
            return 'adolescents'
        elif age >= 16:
            return 'adult'
        return None
    

class PasswordResetOTP(models.Model):
    user          = models.ForeignKey(Users, on_delete=models.CASCADE)
    otp           = models.CharField(_('OTP'), max_length = 6, blank = True, null = True)
    created_at    = models.DateTimeField(_('Created AT'), blank=True, null=True)
    expires_at    = models.DateTimeField(_('Expires At'), blank=True, null=True)
    
    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = datetime.now()
        if not self.expires_at:
            self.expires_at = datetime.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        return datetime.now() <= self.expires_at
