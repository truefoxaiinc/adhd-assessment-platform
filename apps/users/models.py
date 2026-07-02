import secrets

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from django.utils.crypto import constant_time_compare, salted_hmac


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
    is_staff              = models.BooleanField(default = False)
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


class OAuthProvider(models.TextChoices):
    GOOGLE = 'google', _('Google')
    FACEBOOK = 'facebook', _('Facebook')


class OAuthAccount(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='oauth_accounts')
    provider = models.CharField(_('Provider'), max_length=50, choices=OAuthProvider.choices)
    provider_subject = models.CharField(_('Provider Subject'), max_length=255)
    email = models.EmailField(_('Email'), max_length=255, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _("OAuth Account")
        verbose_name_plural = _("OAuth Accounts")
        db_table = 'OAuthAccount'
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'provider_subject'],
                name='uniq_oauth_provider_subject',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'provider']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.provider}:{self.provider_subject}"
    

class PasswordResetOTP(models.Model):
    user          = models.ForeignKey(Users, on_delete=models.CASCADE)
    otp           = models.CharField(_('OTP'), max_length = 6, blank = True, null = True)
    otp_hash      = models.CharField(_('OTP Hash'), max_length=128, blank=True, null=True)
    reset_token_hash = models.CharField(_('Reset Token Hash'), max_length=128, blank=True, null=True)
    is_verified   = models.BooleanField(default=False)
    is_used       = models.BooleanField(default=False)
    created_at    = models.DateTimeField(_('Created AT'), blank=True, null=True)
    expires_at    = models.DateTimeField(_('Expires At'), blank=True, null=True)
    verified_at   = models.DateTimeField(_('Verified At'), blank=True, null=True)
    used_at       = models.DateTimeField(_('Used At'), blank=True, null=True)

    OTP_SALT = "users.password_reset_otp"
    RESET_TOKEN_SALT = "users.password_reset_token"

    @classmethod
    def _hash_value(cls, value, salt):
        return salted_hmac(salt, value).hexdigest()

    @classmethod
    def create_for_user(cls, user, otp=None):
        raw_otp = otp or f"{secrets.randbelow(1_000_000):06d}"
        now = timezone.now()
        cls.objects.filter(user=user, is_used=False).update(is_used=True, used_at=now)
        instance = cls.objects.create(
            user=user,
            otp_hash=cls._hash_value(raw_otp, cls.OTP_SALT),
            expires_at=now + timedelta(minutes=10),
        )
        return instance, raw_otp

    def verify_otp(self, raw_otp):
        if self.is_used or self.is_verified or not self.otp_hash:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return constant_time_compare(
            self.otp_hash,
            self._hash_value(raw_otp, self.OTP_SALT),
        )

    def issue_reset_token(self):
        raw_token = secrets.token_urlsafe(32)
        now = timezone.now()
        self.reset_token_hash = self._hash_value(raw_token, self.RESET_TOKEN_SALT)
        self.is_verified = True
        self.verified_at = now
        self.expires_at = now + timedelta(minutes=10)
        self.otp_hash = None
        self.save(update_fields=['reset_token_hash', 'is_verified', 'verified_at', 'expires_at', 'otp_hash'])
        return raw_token

    def verify_reset_token(self, raw_token):
        if self.is_used or not self.is_verified or not self.reset_token_hash:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return constant_time_compare(
            self.reset_token_hash,
            self._hash_value(raw_token, self.RESET_TOKEN_SALT),
        )

    def mark_used(self):
        self.is_used = True
        self.used_at = timezone.now()
        self.reset_token_hash = None
        self.save(update_fields=['is_used', 'used_at', 'reset_token_hash'])
    
    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        return bool(self.expires_at and timezone.now() <= self.expires_at and not self.is_used)
