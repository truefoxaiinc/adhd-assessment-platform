from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import PushDevice
from apps.notifications.serializers import (
    PushDeviceResponseSerializer,
    RegisterPushDeviceSerializer,
    UnregisterPushDeviceSerializer,
)
from helpers.response import ResponseInfo


def _response(message, data=None, http_status=status.HTTP_200_OK):
    payload = ResponseInfo(
        message=message,
        status_code=http_status,
        data=data or {},
    ).response
    return Response(payload, status=http_status)


class RegisterPushDeviceApiView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=['Notifications'], request_body=RegisterPushDeviceSerializer)
    def post(self, request):
        serializer = RegisterPushDeviceSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            payload = ResponseInfo(
                status=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                message='Invalid device registration request',
                errors=serializer.errors,
            ).response
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        device = serializer.save()
        return _response(
            'Device registered',
            PushDeviceResponseSerializer(device).data,
            status.HTTP_201_CREATED if device.was_created else status.HTTP_200_OK,
        )


class UnregisterPushDeviceApiView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=['Notifications'], request_body=UnregisterPushDeviceSerializer)
    def delete(self, request):
        serializer = UnregisterPushDeviceSerializer(data=request.data)
        if not serializer.is_valid():
            payload = ResponseInfo(
                status=False,
                status_code=status.HTTP_400_BAD_REQUEST,
                message='Invalid device unregistration request',
                errors=serializer.errors,
            ).response
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        PushDevice.objects.filter(
            user=request.user,
            token=serializer.validated_data['token'],
        ).update(is_active=False)
        return _response('Device unregistered')
