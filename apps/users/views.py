from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_object_or_none, get_token_user_or_none
from helpers.response import ResponseInfo
from rest_framework.permissions import IsAuthenticated
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
    Users,
    PasswordResetOTP
)
from drf_yasg import openapi
from helpers.custom_messages import _success,_record_not_found
from .schemas import (
    GetUserProfileDetailSchema
)
from apps.authentication.schemas import (
    GetLoginResponseSchema
)
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework_simplejwt.tokens import RefreshToken
import jwt
import requests
import logging

logger = logging.getLogger(__name__)


class UserRegistrationApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(UserRegistrationApiView, self).__init__(**kwargs)

    serializer_class = UserRegistrationSerializer

    @swagger_auto_schema(tags=["Users"],operation_id='Registration',operation_description="This API allows the users to enrol to this system with basic particular datas",)
    def post(self, request):
        try:
            user_instance = get_object_or_none(Users,pk=request.data.get('id', None))

            serializer = self.serializer_class(user_instance, data=request.data, context = {'request' : request})
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
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetUserProfileDetailApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(GetUserProfileDetailApiView, self).__init__(**kwargs)
        
    serializer_class = GetUserProfileDetailSchema
    permission_classes = (IsAuthenticated,)

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
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 


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
            
            user_instance = get_object_or_none(Users, email=email)
            otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            
            PasswordResetOTP.objects.create(user=user_instance,otp=otp)
            
            from apps.users.tasks import send_otp_email_task
            send_otp_email_task.delay(email, otp)

            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["status"] = True
            self.response_format["message"] = _success
            return Response(self.response_format, status=status.HTTP_201_CREATED)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordResetOTPVerifyApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(PasswordResetOTPVerifyApiView, self).__init__(**kwargs)

    serializer_class = PasswordResetOTPVerifySerializer

    @swagger_auto_schema(tags=["Forget Password"],operation_id='Password Reset OTP Verify',operation_description="This API allows the users to verify OTP",)
    def post(self, request):
        try:
            user_instance = get_object_or_none(Users, email=request.data.get('email', None))
            serializer = self.serializer_class(user_instance,data=request.data, context = {'request' : request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
            
            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["status"] = True
            self.response_format["message"] = _success
            return Response(self.response_format, status=status.HTTP_200_OK)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordChangeApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(PasswordChangeApiView, self).__init__(**kwargs)

    serializer_class = PasswordResetChangeSerializer

    @swagger_auto_schema(tags=["Forget Password"],operation_id='Password Changing API',operation_description="This API allows the users to change their password",)
    def post(self, request):
        try:
            user_instance = get_object_or_none(Users, email=request.data.get('email', None))
            serializer = self.serializer_class(user_instance,data=request.data, context = {'request' : request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)
            
            serializer.save()
            
            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["status"] = True
            self.response_format["message"] = _success
            return Response(self.response_format, status=status.HTTP_201_CREATED)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SocialLoginView(APIView):
    serializer_class = SocialLoginSerializer

    @swagger_auto_schema(tags=["Social Login"],request_body=SocialLoginSerializer,operation_id='Social Login API',operation_description="This API allows the users to login using social media accounts",)
    def post(self, request):
        provider = request.data.get('provider')
        token = request.data.get('id_token')
        
        if not provider or not token:
            return Response({'error': 'Missing provider or token'}, status=400)
        
        try:
            if provider == 'google':
                payload = jwt.decode(token, options={"verify_signature": False})
                if payload.get('iss') != 'https://accounts.google.com':
                    return Response({'error': 'Invalid Google token'}, status=401)
                
                logger.info("Google payload: %s", payload)
                
                email = payload.get('email')
                name_parts = payload.get('name', '').split()
                username = f"google_{payload['sub']}"[:300]  # Unique username
                dob = None  # Not in Google token
                
                logger.info("name_parts: %s", name_parts)
                logger.info("username: %s", username)

                if not email:
                    return Response({'error': 'No email in Google token'}, status=400)
            
            elif provider == 'facebook':
                fb_response = requests.get(
                    f"https://graph.facebook.com/me?access_token={token}&fields=id,email,name,birthday",
                    timeout=10
                )
                if fb_response.status_code != 200:
                    return Response({'error': 'Invalid Facebook token'}, status=401)
                
                fb_data = fb_response.json()
                email = fb_data.get('email', f"fb_{fb_data['id']}@facebook.com")
                name_parts = fb_data.get('name', '').split()
                username = f"fb_{fb_data['id']}"[:300]
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
                return Response({'error': 'Unsupported provider'}, status=400)
            
            # Create or update Users model
            user, created = Users.objects.get_or_create(
                email=email,
                defaults={
                    'username': username,
                    'dob': dob,
                    # Other fields use defaults: is_staff=True, etc.
                }
            )
            
            if not created:
                # Update existing user
                user.username = username
                user.dob = dob
                user.save()
            
            # Generate JWT
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'success': True,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'dob': user.dob.isoformat() if user.dob else None,
                    'is_verified': user.is_verified,
                    'is_staff': user.is_staff
                }
            })
            
        except jwt.DecodeError:
            return Response({'error': 'Invalid token format'}, status=401)
        except Exception as e:
            return Response({'error': f'Login failed: {str(e)}'}, status=500)
        
        
