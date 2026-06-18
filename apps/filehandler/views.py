from apps.filehandler.serializers import VideoUploadSerializer,AdhdContentSerializer
from apps.progresstracker.services.track_services import ProgressTrackerActions
from helpers.helper import get_token_user_or_none
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.filehandler.services.files_services import FilesActions
from .models import AdhdContent
import os,boto3
import mimetypes
from django.conf import settings
from drf_yasg import openapi

class FetchS3Files(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["Files"],operation_id='FilesFetch',operation_description="This API used to fetch files from s3",      
                          manual_parameters=[
            openapi.Parameter(
                'is_management',
                openapi.IN_QUERY,
                description="True for management files (daily prefixes), False for assessment files",
                type=openapi.TYPE_BOOLEAN,
                default=False
            )
        ],)
    def get(self, request):
        try:
            is_management   = "management" if request.GET.get("is_management") in ['True',True,"true"] else "assessment"
            user_instance   = get_token_user_or_none(request)
            day_of_files    = ProgressTrackerActions.get_days_for_the_file(user_instance)
            age_group       = user_instance.age_category if user_instance else "adult"

            if is_management == "assessment":
                prefix = f"media/adhd/{is_management}/{age_group}/"
                file_list = FilesActions.get_assessment_files(request,prefix)

                return Response(
                    {
                        "message": "Success",
                        "status": True,
                        "data": file_list
                    },
                    status=status.HTTP_200_OK,
                )
            

            prefixes = []
            for day in day_of_files:
                prefixes.append(f"media/adhd/{is_management}/{age_group}/day-{day}/")

            file_list = FilesActions.get_management_files(request,prefixes)

            return Response(
                {
                    "message": "Success",
                    "status": True,
                    "data": file_list
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"message": f"Exception - {str(e)}", "status": False},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        


class ListAllFiles(APIView):
    permission_classes = [IsAuthenticated]

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
                )
                .order_by("day", "file_type", "order_number")
            )

            serializer = AdhdContentSerializer(
                queryset,
                many=True,
                context={"unlocked_days": unlocked_days},
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


class FileUploadView(APIView):
    serializer_class = VideoUploadSerializer

    @swagger_auto_schema(tags=["S3 Files"],request_body=VideoUploadSerializer,operation_id='file-upload-s3',operation_description="This API use for file upload to s3",)
    def post(self, request):
        age_group             = request.data.get("age_group")
        day                   = int(request.data.get("day"))
        order_number          = int(request.data.get("order_number"))
        file_type             = request.data.get("file_type", "video")
        is_management         = "management" if request.data.get("is_management") in ['True',True,"true"] else "assessment"

        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "File is required"}, status=status.HTTP_400_BAD_REQUEST)

        ext = os.path.splitext(uploaded_file.name)[1] or ".mp4"

        if is_management == "assessment":
            s3_key = f"media/adhd/{is_management}/{age_group}/{order_number}{ext}"
        else:
            s3_key = f"media/adhd/{is_management}/{age_group}/day-{day}/{file_type}/{order_number}{ext}"

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=settings.AWS_S3_CLIENT_CONFIG,
        )

        content_type = (
            getattr(uploaded_file, "content_type", None)
            or mimetypes.guess_type(uploaded_file.name)[0]
            or "application/octet-stream"
        )
        s3_client.upload_fileobj(
            uploaded_file,
            settings.AWS_STORAGE_BUCKET_NAME,
            s3_key,
            ExtraArgs={"ContentType": content_type},
            Config=settings.AWS_S3_TRANSFER_CONFIG,
        )
        file_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=3600,
        )

        return Response(
            {"detail": "Uploaded", "s3_key": s3_key, "file_url": file_url},
            status=status.HTTP_201_CREATED,
        )



class UpdateLearningProgress(APIView):
    permission_classes = [IsAuthenticated]
    

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
            filetype, day_completed, order_number = request.data.get("filetype"), request.data.get("day_completed"), request.data.get("order_number")
            user_instance = get_token_user_or_none(request)
            ProgressTrackerActions.update_learning_progress(user_instance, filetype, day_completed, order_number)

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
