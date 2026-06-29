from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_object_or_none
from helpers.response import ResponseInfo
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from helpers.custom_messages import _success,_record_not_found
import  os,sys
from .serializers import LoginSerializer, LogoutSerializer
from apps.users.models import Users
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from helpers.exceptions.exceptions import safe_exception_response
from .schemas import  (
            GetLoginResponseSchema,
        )

class LoginApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(LoginApiView, self).__init__(**kwargs)

    serializer_class = LoginSerializer

    @swagger_auto_schema(tags=["Authentication"],operation_id='login',operation_description="This API allows users to log in using their email and password. Upon successful authentication, it returns a bearer token and a refresh token in the response, enabling secure access to protected resources.",)
    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            email       = serializer.validated_data['email']
            password    = serializer.validated_data['password']

            authenticated_user = authenticate(username=email, password=password)
            if not authenticated_user:
                self.response_format['status_code'] = status.HTTP_401_UNAUTHORIZED
                self.response_format["status"] = False
                self.response_format["message"] = "Invalid credentials"
                return Response(self.response_format, status=status.HTTP_401_UNAUTHORIZED)

            if not authenticated_user.is_active:
                self.response_format['status_code'] = status.HTTP_403_FORBIDDEN
                self.response_format["status"] = False
                self.response_format["message"] = "Account is disabled"
                return Response(self.response_format, status=status.HTTP_403_FORBIDDEN)
            
            data = GetLoginResponseSchema(authenticated_user, context={'request': request}).data
            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["status"] = True
            self.response_format["message"] = _success
            self.response_format["data"] = data
            return Response(self.response_format, status=status.HTTP_200_OK)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class LogoutApiView(generics.GenericAPIView):
    serializer_class = LogoutSerializer

    @swagger_auto_schema(tags=["Authentication"],operation_id='logout',operation_description="This API invalidates a refresh token so the user is logged out and cannot refresh JWT access.")
    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                self.response_format = ResponseInfo().response
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format['status'] = False
                self.response_format['errors'] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            refresh_token = serializer.validated_data['refresh']
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError as e:
                self.response_format = ResponseInfo().response
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format['status'] = False
                self.response_format['message'] = 'Invalid refresh token'
                self.response_format['errors'] = {'refresh': ['Invalid refresh token']}
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            self.response_format = ResponseInfo().response
            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format['status'] = True
            self.response_format['message'] = _success
            self.response_format['data'] = {}
            return Response(self.response_format, status=status.HTTP_200_OK)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})
