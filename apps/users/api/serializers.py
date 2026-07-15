import re
from rest_framework import serializers
from apps.users.models import Users,GenderCategory
from apps.users.services.registration_service import RegistrationService
from django.utils.translation import gettext_lazy as _
from helpers.helper import get_object_or_none


class NullableDateField(serializers.DateField):
    def to_internal_value(self, data):
        if data == '':
            return None
        else:
            return super().to_internal_value(data)


class UserRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    password = serializers.CharField(required=True, write_only=True)

    class Meta:
        model = Users
        fields = ['username', 'email', 'password']

    def validate(self, attrs):
        email = attrs.get('email', '')
        username = attrs.get('username', None)
        password = attrs.get('password', None)

        user_query_set = Users.objects.filter(email=email)
        user_object = Users.objects.filter(username=username)

        if username is not None:
            if not re.match("^[a-zA-Z0-9._@]*$", username):
                raise serializers.ValidationError({'username':("Enter a valid Username. Only alphabets, numbers, '@', '_', and '.' are allowed.")})

        if user_object.exists():
            raise serializers.ValidationError({"username":('Username already exists!')})

        if user_query_set.exists():
            raise serializers.ValidationError({"email":('Email already exists!')})

        if password is not None and (len(password) < 8 or not any(char.isupper() for char in password) or not any(char.islower() for char in password) or not any(char.isdigit() for char in password) or not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?\'\"\\/~`' for char in password)):
            raise serializers.ValidationError({"password":('Must Contain 8 Characters, One Uppercase, One Lowercase, One Number and One Special Character')})

        return super().validate(attrs)

    def create(self, validated_data):
        return RegistrationService.create_user(
            username=validated_data.get('username'),
            email=validated_data.get('email'),
            password=validated_data.get('password'),
        )


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
    is_last     = serializers.BooleanField(required=False)

    class Meta:
        model = Users
        fields = ['id','username','email','password','dob','gender','country','height','weight','profile_image','is_last']

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
        if 'is_last' in validated_data:
            instance.is_last = validated_data.get('is_last')
            if instance.is_last:
                instance.is_first = False
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
        user_instance   = get_object_or_none(Users,email=email)

        if not user_instance:
            raise serializers.ValidationError({"email": "No user found with this email address"})
        
        return super().validate(attrs)
    
    
class PasswordResetChangeSerializer(serializers.Serializer):
    email       = serializers.EmailField()
    reset_token = serializers.CharField(write_only=True)
    password    = serializers.CharField(min_length=8, write_only=True)

    class Meta:
        model = Users
        fields = ['email','reset_token','password']
    
    def validate(self, attrs):
        email           = attrs.get('email', '')
        password        = attrs.get('password', '')
        user_instance   = get_object_or_none(Users,email=email)

        if not user_instance:
            raise serializers.ValidationError({"email": "No user found with this email address"})
        
        if password is not None and (len(password) < 8 or not any(char.isupper() for char in password) or not any(char.islower() for char in password) or not any(char.isdigit() for char in password) or not any(char in '!@#$%^&*()_+-=[]{}|;:,.<>?\'\"\\/~`' for char in password)):
            raise serializers.ValidationError({"password":('Must Contain 8 Characters, One Uppercase, One Lowercase, One Number and One Special Character')})
        
        return super().validate(attrs)


class SocialLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=['google', 'facebook'], required=True)
    id_token = serializers.CharField(required=True, trim_whitespace=True)

    def validate_provider(self, value):
        return value.lower()

    class Meta:
        model = Users
        fields = ['provider','id_token']


