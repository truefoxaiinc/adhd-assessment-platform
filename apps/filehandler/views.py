from apps.filehandler.serializers import (
    AdhdContentSerializer,
    UpdateLearningProgressSerializer,
)
from apps.progresstracker.services.track_services import ProgressTrackerActions
from helpers.helper import get_token_user_or_none
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.filehandler.services.files_services import FilesActions
from .models import AdhdContent, ContentStatus
from drf_yasg import openapi
        


class ListAllFiles(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=["Files"],
        operation_id="list-all-files",
        operation_description="Fetch ADHD content files",
        manual_parameters=[
            openapi.Parameter(
                'is_management',
                openapi.IN_QUERY,
                description='True for management files, False for assessment files',
                type=openapi.TYPE_BOOLEAN,
                default=False
            )
        ]
    )
    def get(self, request):
        try:
            is_management = request.GET.get("is_management") in ["True", "true", True]

            user_instance = get_token_user_or_none(request)
            age_group = user_instance.age_category if user_instance and user_instance.age_category else "adult"
            unlocked_days = ProgressTrackerActions.get_days_for_the_file(user_instance) or [1]

            queryset = (
                AdhdContent.objects
                .filter(
                    is_management=is_management,
                    age_group=age_group,
                    status=ContentStatus.PUBLISHED,
                )
                .order_by("day", "file_type", "order_number")
            )

            serializer = AdhdContentSerializer(
                queryset,
                many=True,
                context={"unlocked_days": unlocked_days, "request": request},
            )

            return Response(
                {
                    "message": "Success",
                    "status": True,
                    "data": serializer.data
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "message": f"Exception - {str(e)}",
                    "status": False
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,)


class SaveFeedbackforAIAssessment(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["Files"],operation_id='save-feedback',operation_description="This API used to save feedback from users",)
    def get(self, request):
        try:
            FilesActions.save_feedback(request)

            return Response(
                {
                    "message": "Success",
                    "status": True,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"message": f"Exception - {str(e)}", "status": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UpdateLearningProgress(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateLearningProgressSerializer
    

    @swagger_auto_schema(tags=["Files"],operation_id='update-learning-progress',operation_description="This API used to update learning progress",
                         manual_parameters=[
            openapi.Parameter(
                'filetype',
                openapi.IN_QUERY,
                description="Type of the file completed (video/file)",
                type=openapi.TYPE_STRING,
                enum=['video', 'file']
            ),
            openapi.Parameter(
                'day_completed',
                openapi.IN_QUERY,
                description="Day of the file completed",
                type=openapi.TYPE_INTEGER,
            ),
            openapi.Parameter(
                'order_number',
                openapi.IN_QUERY,
                description="Order number of the file completed",
                type=openapi.TYPE_INTEGER,
            ),
        ]
    )
    def post(self, request):
        try:
            user_instance = get_token_user_or_none(request)
            serializer = self.serializer_class(
                data=request.data,
                context={"request": request},
            )
            if not serializer.is_valid():
                return Response(
                    {
                        "message": "Validation Error",
                        "status": False,
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ProgressTrackerActions.update_learning_progress(
                user_instance,
                serializer.validated_data["filetype"],
                serializer.validated_data["day_completed"],
                serializer.validated_data["order_number"],
            )

            return Response(
                {
                    "message": "Success",
                    "status": True,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"message": f"Exception - {str(e)}", "status": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
