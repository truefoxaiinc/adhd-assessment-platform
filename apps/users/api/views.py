from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_object_or_none, get_token_user_or_none
from helpers.response import ResponseInfo
from helpers.exceptions.exceptions import safe_exception_response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from helpers.custom_messages import _success
import  os,sys,random
from django.db.models import Q
from .serializers import (
    SocialLoginSerializer,
    UserRegistrationSerializer,
    UserUpdateProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetOTPVerifySerializer,
    PasswordResetChangeSerializer
)
from apps.users.models import (
    Users
)
from apps.users.services.password_reset_service import PasswordResetService
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

    def _build_success_response(self, user, http_status=status.HTTP_200_OK):
        data = GetLoginResponseSchema(user, context={'request': self.request}).data
        self.response_format['status_code'] = http_status
        self.response_format['status'] = True
        self.response_format['message'] = _success
        self.response_format['data'] = data
        return Response(self.response_format, status=http_status)

    def _get_unique_username(self, base_username):
        username = base_username[:300]
        if not Users.objects.filter(username=username).exists():
            return username

        suffix = random.randint(1000, 9999)
        return f"{base_username[:294]}_{suffix}"[:300]

    @swagger_auto_schema(tags=["Social Login"],request_body=SocialLoginSerializer,operation_id='Social Login API',operation_description="This API allows the users to login using social media accounts",)
    def post(self, request):
        self.request = request
        provider = (request.data.get('provider') or '').lower()
        token = request.data.get('id_token')
        
        if not provider or not token:
            self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            self.response_format['status'] = False
            self.response_format['message'] = 'Missing provider or token'
            return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if provider == 'google':
                audience = settings.GOOGLE_OAUTH_CLIENT_IDS[0] if settings.GOOGLE_OAUTH_CLIENT_IDS else None
                payload = google_id_token.verify_oauth2_token(
                    token,
                    google_requests.Request(),
                    audience,
                )

                if payload.get('iss') not in ['accounts.google.com', 'https://accounts.google.com']:
                    self.response_format['status_code'] = status.HTTP_401_UNAUTHORIZED
                    self.response_format['status'] = False
                    self.response_format['message'] = 'Invalid Google token issuer'
                    return Response(self.response_format, status=status.HTTP_401_UNAUTHORIZED)

                if settings.GOOGLE_OAUTH_CLIENT_IDS and payload.get('aud') not in settings.GOOGLE_OAUTH_CLIENT_IDS:
                    self.response_format['status_code'] = status.HTTP_401_UNAUTHORIZED
                    self.response_format['status'] = False
                    self.response_format['message'] = 'Google token audience mismatch'
                    return Response(self.response_format, status=status.HTTP_401_UNAUTHORIZED)
                
                logger.info("Google payload: %s", payload)
                
                email = payload.get('email')
                username = f"google_{payload['sub']}"[:300]
                is_verified = bool(payload.get('email_verified', False))
                
                logger.info("username: %s", username)

                if not email:
                    self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                    self.response_format['status'] = False
                    self.response_format['message'] = 'No email in Google token'
                    return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
            
            elif provider == 'facebook':
                fb_response = requests.get(
                    f"https://graph.facebook.com/me?access_token={token}&fields=id,email,name,birthday",
                    timeout=10
                )
                if fb_response.status_code != 200:
                    self.response_format['status_code'] = status.HTTP_401_UNAUTHORIZED
                    self.response_format['status'] = False
                    self.response_format['message'] = 'Invalid Facebook token'
                    return Response(self.response_format, status=status.HTTP_401_UNAUTHORIZED)
                
                fb_data = fb_response.json()
                email = fb_data.get('email', f"fb_{fb_data['id']}@facebook.com")
                username = f"fb_{fb_data['id']}"[:300]
                is_verified = bool(fb_data.get('email'))
                # Parse DOB if available (format: MM/DD/YYYY or MM/YYYY)
                dob_str = fb_data.get('birthday')
                dob = None
                if dob_str:
                    try:
                        from datetime import datetime
                        dob = datetime.strptime(dob_str, '%m/%d/%Y').date() if '/' in dob_str else None
                    except:
                        pass
            
            else:
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format['status'] = False
                self.response_format['message'] = 'Unsupported provider'
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
            
            # Create or update Users model
            user, created = Users.objects.get_or_create(
                email=email,
                defaults={
                    'username': self._get_unique_username(username),
                    'dob': dob if provider == 'facebook' else None,
                    'is_verified': is_verified,
                }
            )
            
            if not created:
                update_fields = []
                if not user.username:
                    user.username = self._get_unique_username(username)
                    update_fields.append('username')
                if is_verified and not user.is_verified:
                    user.is_verified = True
                    update_fields.append('is_verified')
                if provider == 'facebook' and dob and not user.dob:
                    user.dob = dob
                    update_fields.append('dob')
                if update_fields:
                    user.save(update_fields=update_fields)
            
            return self._build_success_response(
                user,
                status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
            
        except ValueError:
            self.response_format['status_code'] = status.HTTP_401_UNAUTHORIZED
            self.response_format['status'] = False
            self.response_format['message'] = 'Invalid token format'
            return Response(self.response_format, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})
        
        
