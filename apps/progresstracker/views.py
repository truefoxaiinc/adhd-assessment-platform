from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_object_or_none, get_token_user_or_none
from helpers.response import ResponseInfo
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from helpers.custom_messages import _success
import  os,sys,random
from django.db.models import Q
from apps.progresstracker.serializers import (
    SaveDailyCompletedStatusSerializer
)
from apps.users.models import (
    Users,
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


class SaveDailyCompletedStatus(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(SaveDailyCompletedStatus, self).__init__(**kwargs)

    serializer_class = SaveDailyCompletedStatusSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["Progress Tracker"],operation_id='save-progress-tracker',operation_description="This API allows to save the progress of users after watching the videos",)
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
