import re
from rest_framework import serializers
from apps.users.models import  PasswordResetOTP, Users,GenderCategory
from django.utils.translation import gettext_lazy as _
from helpers.helper import get_object_or_none
from django.utils import timezone


class NullableDateField(serializers.DateField):
    def to_internal_value(self, data):
        if data == '':
            return None
        else:
            return super().to_internal_value(data)


class UserRegistrationSerializer(serializers.ModelSerializer):
    id                      = serializers.IntegerField(allow_null=True, required=False)
    username                  = serializers.CharField(required=True)
    email                     = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    password                  = serializers.CharField(required=False)
    is_admin                  = serializers.BooleanField(default=False)
    is_staff                  = serializers.BooleanField(default=False)

    class Meta:
        model = Users
        fields = ['id','username','email','password','is_active','is_admin','is_staff']


    def validate(self, attrs):
        email           = attrs.get('email', '')
        user            = attrs.get('id', None)
        username        = attrs.get('username', None)
        password        = attrs.get('password', None)

        user_query_set = Users.objects.filter(email=email)
        user_object    = Users.objects.filter(username=username)

        if username is not None:
            if not re.match("^[a-zA-Z0-9._@]*$", username):
                raise serializers.ValidationError({'username':("Enter a valid Username. Only alphabets, numbers, '@', '_', and '.' are allowed.")})

        if user is not None:
            user_instance = get_object_or_none(Users,pk=user)
            user_query_set = user_query_set.exclude(pk=user_instance.pk)
            user_object    = user_object.exclude(pk=user_instance.pk)

        if user_object.exists():
            raise serializers.ValidationError({"username":('Username already exists!')})

        if user_query_set.exists():
            raise serializers.ValidationError({"email":('Email already exists!')})

        if password is not None and (len(password) < 8 or not any(char.isupper() for char in password) or not any(char.islower() for char in password) or not any(char.isdigit() for char in password) or not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?\'\"\\/~`' for char in password)):
            raise serializers.ValidationError({"password":('Must Contain 8 Characters, One Uppercase, One Lowercase, One Number and One Special Character')})


        return super().validate(attrs)



    def create(self, validated_data):
        password                  = validated_data.get('password')

        instance                  = Users()
        instance.username         = validated_data.get('username')
        instance.email            = validated_data.get('email')
        instance.set_password(password)
        instance.is_active        = validated_data.get('is_active')
        instance.is_admin         = validated_data.get('is_admin')
        instance.is_staff         = True
        instance.is_password_reset_required = True
        instance.save()

        return instance


    def update(self, instance, validated_data):
        password = validated_data.get('password','')

        instance.username = validated_data.get('username')
        instance.email = validated_data.get('email')
        if password:
            instance.set_password(password)

        if validated_data.get('is_active',''):
            instance.is_active = validated_data.get('is_active')


        if validated_data.get('is_admin',''):
            instance.is_admin = validated_data.get('is_admin')

        if validated_data.get('v',''):
            instance.is_staff = validated_data.get('is_staff')

        instance.save()

        return instance


class UserUpdateProfileSerializer(serializers.ModelSerializer):
    id        = serializers.IntegerField(allow_null=True, required=True)
    username    = serializers.CharField(required=True)
    email       = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    password    = serializers.CharField(required=False, allow_null=True, allow_blank=True, write_only=True)
    dob         = serializers.DateField(required=False, allow_null=True)
    gender      = serializers.ChoiceField(choices=GenderCategory.choices, required=False, allow_null=True, allow_blank=True)
    country     = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    height      = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    weight      = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Users
        fields = ['id','username','email','password','dob','gender','country','height','weight','profile_image']

    def validate(self, attrs):
        email           = attrs.get('email', '')
        user            = attrs.get('id', None)
        username        = attrs.get('username', None)
        password        = attrs.get('password', None)

        user_query_set = Users.objects.filter(email=email)
        user_object    = Users.objects.filter(username=username)

        if username is not None:
            if not re.match("^[a-zA-Z0-9._@]*$", username):
                raise serializers.ValidationError({'username':("Enter a valid Username. Only alphabets, numbers, '@', '_', and '.' are allowed.")})

        if user is not None:
            user_instance = get_object_or_none(Users,pk=user)
            user_query_set = user_query_set.exclude(pk=user_instance.pk)
            user_object    = user_object.exclude(pk=user_instance.pk)

        if user_object.exists():
            raise serializers.ValidationError({"username":('Username already exists!')})

        if user_query_set.exists():
            raise serializers.ValidationError({"email":('Email already exists!')})

        if password and (len(password) < 8 or not any(char.isupper() for char in password) or not any(char.islower() for char in password) or not any(char.isdigit() for char in password) or not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?\'\"\\/~`' for char in password)):
            raise serializers.ValidationError({"password":('Must Contain 8 Characters, One Uppercase, One Lowercase, One Number and One Special Character')})
        return super().validate(attrs)


    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        instance.username   = validated_data.get('username', instance.username)
        instance.email      = validated_data.get('email', instance.email)
        instance.dob        = validated_data.get('dob', instance.dob)
        instance.gender     = validated_data.get('gender', instance.gender)
        instance.country    = validated_data.get('country', instance.country)
        instance.height     = validated_data.get('height', instance.height)
        instance.weight     = validated_data.get('weight', instance.weight)
        if 'profile_image' in validated_data:
            instance.profile_image = validated_data.get('profile_image')
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        if not Users.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email address")
        return value
    


class PasswordResetOTPVerifySerializer(serializers.Serializer):
    email       = serializers.EmailField()
    otp         = serializers.CharField(max_length=6)

    class Meta:
        model = Users
        fields = ['email','otp']
    
    def validate(self, attrs):
        email           = attrs.get('email', '')
        otp             = attrs.get('otp', '')
        user_instance   = get_object_or_none(Users,email=email)

        if not user_instance:
            raise serializers.ValidationError({"email": "No user found with this email address"})
        
        otp_obj = PasswordResetOTP.objects.filter(user=user_instance, otp=otp).order_by('-id').first()

        if not otp_obj:
            raise serializers.ValidationError({"otp": "Invalid OTP"})

        if otp_obj.expires_at < timezone.now():
            raise serializers.ValidationError({"otp": "OTP has expired"})
        
        return super().validate(attrs)
    
    
class PasswordResetChangeSerializer(serializers.Serializer):
    email       = serializers.EmailField()
    password    = serializers.CharField(min_length=8, write_only=True)

    class Meta:
        model = Users
        fields = ['email','password']
    
    def validate(self, attrs):
        email           = attrs.get('email', '')
        password        = attrs.get('password', '')
        user_instance   = get_object_or_none(Users,email=email)

        if not user_instance:
            raise serializers.ValidationError({"email": "No user found with this email address"})
        
        if password is not None and (len(password) < 8 or not any(char.isupper() for char in password) or not any(char.islower() for char in password) or not any(char.isdigit() for char in password) or not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?\'\"\\/~`' for char in password)):
            raise serializers.ValidationError({"password":('Must Contain 8 Characters, One Uppercase, One Lowercase, One Number and One Special Character')})
        
        return super().validate(attrs)
    
    def update(self, instance, validated_data):
        password = validated_data.get('password')
        instance.set_password(password)
        instance.save()
        return instance


class SocialLoginSerializer(serializers.Serializer):
    provider                  = serializers.CharField(required=True)
    id_token                  = serializers.CharField(required=True)
    class Meta:
        model = Users
        fields = ['provider','id_token']


