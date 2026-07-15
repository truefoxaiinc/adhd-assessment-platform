from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_object_or_none, get_token_user_or_none
from helpers.response import ResponseInfo
from helpers.exceptions.exceptions import safe_exception_response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from helpers.custom_messages import _success
import hashlib
import hmac
import os,sys,random
import re
import time
from django.db.models import Q
from django.db import transaction
from .serializers import (
    SocialLoginSerializer,
    UserRegistrationSerializer,
    UserUpdateProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetOTPVerifySerializer,
    PasswordResetChangeSerializer
)
from apps.users.models import (
    OAuthAccount,
    OAuthProvider,
    Users
)
from apps.users.services.password_reset_service import PasswordResetService
from apps.users.services.registration_service import RegistrationService
from drf_yasg import openapi
from helpers.custom_messages import _success,_record_not_found
from apps.users.schemas import (
    GetUserProfileDetailSchema
)
from apps.authentication.schemas import (
    GetLoginResponseSchema
)
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
import requests
import logging
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

logger = logging.getLogger(__name__)


class UserRegistrationApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(UserRegistrationApiView, self).__init__(**kwargs)

    serializer_class = UserRegistrationSerializer

    @swagger_auto_schema(tags=["Users"],operation_id='Registration',operation_description="This API allows the users to enrol to this system with basic particular datas",)
    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data, context = {'request' : request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            authenticated_user = serializer.save()

            data = GetLoginResponseSchema(authenticated_user, context={'request': request}).data
            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["status"] = True
            self.response_format["message"] = _success
            self.response_format["data"] = data
            return Response(self.response_format, status=status.HTTP_201_CREATED)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class UserUpdateProfileApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(UserUpdateProfileApiView, self).__init__(**kwargs)

    serializer_class = UserUpdateProfileSerializer
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @swagger_auto_schema(tags=["Profile"],operation_id='Profile Updation',operation_description="This API allows the users to complete their profile updation with particular details",)
    def post(self, request):
        try:

            user_id = request.data.get('id', None)
            if not user_id:
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["message"] = "Please Provide the user id"
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            token_user = get_token_user_or_none(request)
            if token_user and str(token_user.id) != str(user_id):
                self.response_format['status_code'] = status.HTTP_403_FORBIDDEN
                self.response_format["status"] = False
                self.response_format["message"] = "You can update only your own profile"
                return Response(self.response_format, status=status.HTTP_403_FORBIDDEN)

            user_instance = get_object_or_none(Users,pk=user_id)
            if user_instance is None:
                self.response_format['status_code'] = status.HTTP_404_NOT_FOUND
                self.response_format["status"] = False
                self.response_format["message"] = _record_not_found
                return Response(self.response_format, status=status.HTTP_404_NOT_FOUND)

            serializer = self.serializer_class(user_instance, data=request.data, context = {'request' : request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            updated_user = serializer.save()

            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["message"] = _success
            self.response_format["status"] = True
            self.response_format["data"] = GetUserProfileDetailSchema(updated_user, context={'request': request}).data
            from django.core.cache import cache
            cache.delete(f'user_profile_{updated_user.id}')
            return Response(self.response_format, status=status.HTTP_201_CREATED)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class GetUserProfileDetailApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(GetUserProfileDetailApiView, self).__init__(**kwargs)
        
    serializer_class = GetUserProfileDetailSchema
    permission_classes = (IsAuthenticated,)
    filter_backends = []

    id = openapi.Parameter('id', openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, description="Optional user id. Defaults to logged-in user.")
    
    @swagger_auto_schema(tags=["Profile"], manual_parameters=[id],operation_id='Profile fetching',operation_description="This API allows fetch the details of a particular user with  user id to show the details in the profile editing page",)
    def get(self, request):
        
        try:
            
            token_user = get_token_user_or_none(request)
            user_id = request.GET.get('id', None) or token_user.id
            if str(token_user.id) != str(user_id):
                self.response_format['status_code'] = status.HTTP_403_FORBIDDEN
                self.response_format["message"] = "You can view only your own profile"
                self.response_format["status"] = False
                return Response(self.response_format, status=status.HTTP_403_FORBIDDEN)


            instance = get_object_or_none(Users, pk=user_id)
            if instance is None:
                self.response_format['status_code'] = status.HTTP_204_NO_CONTENT
                self.response_format["message"] = _record_not_found
                self.response_format["status"] = False
                return Response(self.response_format, status=status.HTTP_200_OK)
                
            data = self.serializer_class(instance, context={'request': request}).data 
            
            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["data"] = data 
            self.response_format["message"] = _success
            self.response_format["status"] = True
            
            return Response(self.response_format, status=status.HTTP_200_OK)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class PasswordResetRequestApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(PasswordResetRequestApiView, self).__init__(**kwargs)

    serializer_class = PasswordResetRequestSerializer

    @swagger_auto_schema(tags=["Forget Password"],operation_id='Password Reset Request',operation_description="This API allows the users to send the email to their typed mail id",)
    def post(self, request):
        try:

            serializer = self.serializer_class(data=request.data, context = {'request' : request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
            
            email = serializer.validated_data.get('email', None)
            PasswordResetService.request_reset(email)

            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["status"] = True
            self.response_format["message"] = _success
            return Response(self.response_format, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            self.response_format["status"] = False
            self.response_format["errors"] = e.detail
            return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class PasswordResetOTPVerifyApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(PasswordResetOTPVerifyApiView, self).__init__(**kwargs)

    serializer_class = PasswordResetOTPVerifySerializer

    @swagger_auto_schema(tags=["Forget Password"],operation_id='Password Reset OTP Verify',operation_description="This API allows the users to verify OTP",)
    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data, context = {'request' : request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            reset_token = PasswordResetService.verify_otp(
                serializer.validated_data.get('email'),
                serializer.validated_data.get('otp'),
            )
            
            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["status"] = True
            self.response_format["message"] = _success
            self.response_format["data"] = {"reset_token": reset_token}
            return Response(self.response_format, status=status.HTTP_200_OK)

        except ValidationError as e:
            self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            self.response_format["status"] = False
            self.response_format["errors"] = e.detail
            return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class PasswordChangeApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(PasswordChangeApiView, self).__init__(**kwargs)

    serializer_class = PasswordResetChangeSerializer

    @swagger_auto_schema(tags=["Forget Password"],operation_id='Password Changing API',operation_description="This API allows the users to change their password",)
    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data, context = {'request' : request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
            
            PasswordResetService.change_password(
                serializer.validated_data.get('email'),
                serializer.validated_data.get('reset_token'),
                serializer.validated_data.get('password'),
            )
            
            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["status"] = True
            self.response_format["message"] = _success
            return Response(self.response_format, status=status.HTTP_201_CREATED)

        except ValidationError as e:
            self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            self.response_format["status"] = False
            self.response_format["errors"] = e.detail
            return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class SocialLoginView(APIView):
    serializer_class = SocialLoginSerializer

    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(SocialLoginView, self).__init__(**kwargs)

    def _error_response(self, message, http_status=status.HTTP_400_BAD_REQUEST, errors=None):
        self.response_format['status_code'] = http_status
        self.response_format['status'] = False
        self.response_format['message'] = message
        if errors is not None:
            self.response_format['errors'] = errors
        return Response(self.response_format, status=http_status)

    def _build_success_response(self, user, http_status=status.HTTP_200_OK):
        data = GetLoginResponseSchema(user, context={'request': self.request}).data
        self.response_format['status_code'] = http_status
        self.response_format['status'] = True
        self.response_format['message'] = _success
        self.response_format['data'] = data
        return Response(self.response_format, status=http_status)

    def _normalize_social_username(self, display_name, fallback_username):
        username = re.sub(r'[^a-zA-Z0-9._@]+', '_', (display_name or '').strip()).strip('._')
        return (username or fallback_username or 'social_user')[:300]

    def _is_social_placeholder_username(self, username, provider):
        if not username:
            return True
        if provider == OAuthProvider.GOOGLE:
            return username.startswith('google_')
        if provider == OAuthProvider.FACEBOOK:
            return username.startswith('fb_')
        return False

    def _get_unique_username(self, base_username):
        username = (base_username or 'social_user')[:300]
        if not Users.objects.filter(username=username).exists():
            return username

        for _ in range(10):
            suffix = random.randint(1000, 999999)
            candidate = f"{username[:293]}_{suffix}"[:300]
            if not Users.objects.filter(username=candidate).exists():
                return candidate

        return f"{username[:267]}_{random.getrandbits(128):032x}"[:300]

    def _parse_facebook_birthday(self, birthday):
        if not birthday:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(birthday, '%m/%d/%Y').date()
        except ValueError:
            return None

    def _verify_google_token(self, token):
        if not settings.GOOGLE_OAUTH_CLIENT_IDS:
            raise ValidationError({'provider': 'Google OAuth client id is not configured'})

        payload = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
        )

        if payload.get('iss') not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValidationError({'id_token': 'Invalid Google token issuer'})

        if payload.get('aud') not in settings.GOOGLE_OAUTH_CLIENT_IDS:
            raise ValidationError({'id_token': 'Google token audience mismatch'})

        if not payload.get('email'):
            raise ValidationError({'id_token': 'No email in Google token'})

        if not payload.get('email_verified'):
            raise ValidationError({'id_token': 'Google email is not verified'})

        provider_subject = payload.get('sub')
        if not provider_subject:
            raise ValidationError({'id_token': 'No subject in Google token'})

        return {
            'provider': OAuthProvider.GOOGLE,
            'provider_subject': provider_subject,
            'email': payload.get('email'),
            'email_verified': True,
            'username': self._normalize_social_username(
                payload.get('name') or payload.get('given_name'),
                f"google_{provider_subject}",
            ),
            'dob': None,
        }

    def _facebook_app_access_token(self):
        if not settings.FACEBOOK_APP_ID or not settings.FACEBOOK_APP_SECRET:
            raise ValidationError({'provider': 'Facebook app id/secret is not configured'})
        return f"{settings.FACEBOOK_APP_ID}|{settings.FACEBOOK_APP_SECRET}"

    def _facebook_appsecret_proof(self, token):
        return hmac.new(
            settings.FACEBOOK_APP_SECRET.encode('utf-8'),
            token.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

    def _verify_facebook_token(self, token):
        app_access_token = self._facebook_app_access_token()
        debug_response = requests.get(
            'https://graph.facebook.com/debug_token',
            params={
                'input_token': token,
                'access_token': app_access_token,
            },
            timeout=10,
        )
        if debug_response.status_code != 200:
            raise ValidationError({'id_token': 'Invalid Facebook token'})

        token_data = debug_response.json().get('data', {})
        if not token_data.get('is_valid'):
            raise ValidationError({'id_token': 'Invalid Facebook token'})

        if str(token_data.get('app_id')) != str(settings.FACEBOOK_APP_ID):
            raise ValidationError({'id_token': 'Facebook token audience mismatch'})

        expires_at = token_data.get('expires_at')
        if expires_at and int(expires_at) < int(time.time()):
            raise ValidationError({'id_token': 'Facebook token has expired'})

        provider_subject = token_data.get('user_id')
        if not provider_subject:
            raise ValidationError({'id_token': 'No user id in Facebook token'})

        profile_response = requests.get(
            'https://graph.facebook.com/me',
            params={
                'access_token': token,
                'appsecret_proof': self._facebook_appsecret_proof(token),
                'fields': 'id,email,name,birthday',
            },
            timeout=10,
        )
        if profile_response.status_code != 200:
            raise ValidationError({'id_token': 'Unable to fetch Facebook profile'})

        profile = profile_response.json()
        if str(profile.get('id')) != str(provider_subject):
            raise ValidationError({'id_token': 'Facebook profile mismatch'})

        email = profile.get('email')
        if not email:
            raise ValidationError({'id_token': 'Facebook account did not return an email address'})

        return {
            'provider': OAuthProvider.FACEBOOK,
            'provider_subject': provider_subject,
            'email': email,
            'email_verified': True,
            'username': self._normalize_social_username(
                profile.get('name'),
                f"fb_{provider_subject}",
            ),
            'dob': self._parse_facebook_birthday(profile.get('birthday')),
        }

    @transaction.atomic
    def _get_or_create_social_user(self, identity):
        oauth_account = (
            OAuthAccount.objects
            .select_related('user')
            .filter(
                provider=identity['provider'],
                provider_subject=identity['provider_subject'],
            )
            .first()
        )

        if oauth_account:
            update_fields = []
            if oauth_account.email != identity['email']:
                oauth_account.email = identity['email']
                update_fields.append('email')
            if oauth_account.email_verified != identity['email_verified']:
                oauth_account.email_verified = identity['email_verified']
                update_fields.append('email_verified')
            if update_fields:
                oauth_account.save(update_fields=update_fields)
            user = oauth_account.user
            user_update_fields = []
            if self._is_social_placeholder_username(user.username, identity['provider']):
                user.username = self._get_unique_username(identity['username'])
                user_update_fields.append('username')
            if identity['email_verified'] and not user.is_verified:
                user.is_verified = True
                user_update_fields.append('is_verified')
            if user_update_fields:
                user.save(update_fields=user_update_fields)
            return oauth_account.user, False

        user, created = Users.objects.get_or_create(
            email=identity['email'],
            defaults={
                'username': self._get_unique_username(identity['username']),
                'dob': identity['dob'],
                'is_verified': identity['email_verified'],
            }
        )

        update_fields = []
        if self._is_social_placeholder_username(user.username, identity['provider']):
            user.username = self._get_unique_username(identity['username'])
            update_fields.append('username')
        if identity['email_verified'] and not user.is_verified:
            user.is_verified = True
            update_fields.append('is_verified')
        if identity['dob'] and not user.dob:
            user.dob = identity['dob']
            update_fields.append('dob')
        if update_fields:
            user.save(update_fields=update_fields)

        OAuthAccount.objects.get_or_create(
            provider=identity['provider'],
            provider_subject=identity['provider_subject'],
            defaults={
                'user': user,
                'email': identity['email'],
                'email_verified': identity['email_verified'],
            },
        )
        if created:
            RegistrationService.ensure_initial_goal(user)
        return user, created

    @swagger_auto_schema(tags=["Social Login"],request_body=SocialLoginSerializer,operation_id='Social Login API',operation_description="This API allows the users to login using social media accounts",)
    def post(self, request):
        self.request = request

        try:
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                return self._error_response(
                    'Invalid social login request',
                    status.HTTP_400_BAD_REQUEST,
                    serializer.errors,
                )

            provider = serializer.validated_data['provider']
            token = serializer.validated_data['id_token']

            if provider == 'google':
                identity = self._verify_google_token(token)
            elif provider == 'facebook':
                identity = self._verify_facebook_token(token)
            else:
                return self._error_response('Unsupported provider', status.HTTP_400_BAD_REQUEST)

            user, created = self._get_or_create_social_user(identity)

            return self._build_success_response(
                user,
                status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        except ValidationError as e:
            return self._error_response(
                'Social login validation failed',
                status.HTTP_401_UNAUTHORIZED,
                e.detail,
            )
        except ValueError:
            return self._error_response('Invalid token format', status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})
        
        
