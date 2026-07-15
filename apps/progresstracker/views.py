from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_object_or_none, get_token_user_or_none
from helpers.response import ResponseInfo
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from helpers.custom_messages import _success
import  os,sys,random
from django.db.models import Q
from apps.progresstracker.models import UserGoal
from apps.progresstracker.serializers import (
    SaveDailyCompletedStatusSerializer,
    UserGoalBulkCreateSerializer,
    UserGoalListItemSerializer,
    UserGoalSerializer,
)
from apps.users.models import (
    Users,
)
from helpers.custom_messages import _success,_record_not_found
from apps.authentication.schemas import (
    GetLoginResponseSchema
)
from helpers.exceptions.exceptions import safe_exception_response
from django.utils import timezone


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


class UserGoalListCreateApiView(generics.GenericAPIView):
    serializer_class = UserGoalBulkCreateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = []

    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(UserGoalListCreateApiView, self).__init__(**kwargs)

    @staticmethod
    def expire_old_first_goals(user):
        UserGoal.objects.filter(
            user=user,
            is_first=True,
            created_at__date__lt=timezone.localdate(),
        ).update(is_first=False)

    @staticmethod
    def build_goal_response(response_format, goals, http_status):
        goals = list(goals)
        response_format['status_code'] = http_status
        response_format["status"] = True
        response_format["message"] = _success
        response_format["is_first"] = any(goal.is_first for goal in goals)
        response_format["is_last"] = any(goal.is_last for goal in goals)
        last_goal = next((goal for goal in reversed(goals) if goal.is_last), None)
        rating_goal = last_goal or (goals[-1] if goals else None)
        response_format["rating"] = rating_goal.rating if rating_goal else 0
        response_format["data"] = UserGoalListItemSerializer(goals, many=True).data
        return response_format

    @swagger_auto_schema(
        tags=["User Goals"],
        operation_id='user-goals-list',
        operation_description="Fetch authenticated user's goals.",
    )
    def get(self, request):
        try:
            self.expire_old_first_goals(request.user)
            goals = UserGoal.objects.filter(user=request.user).order_by('created_at', 'id')

            self.build_goal_response(self.response_format, goals, status.HTTP_200_OK)
            return Response(self.response_format, status=status.HTTP_200_OK)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})

    @swagger_auto_schema(
        tags=["User Goals"],
        request_body=UserGoalBulkCreateSerializer,
        operation_id='user-goals-create',
        operation_description="Add one or more goals for authenticated user.",
    )
    def post(self, request):
        try:
            self.expire_old_first_goals(request.user)
            serializer = self.serializer_class(data=request.data, context={'request': request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            goals = serializer.save()

            self.build_goal_response(self.response_format, goals, status.HTTP_201_CREATED)
            return Response(self.response_format, status=status.HTTP_201_CREATED)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class UserGoalUpdateApiView(generics.GenericAPIView):
    serializer_class = UserGoalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = []

    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(UserGoalUpdateApiView, self).__init__(**kwargs)

    def get_object(self, request, goal_id):
        return UserGoal.objects.filter(id=goal_id, user=request.user).first()

    @swagger_auto_schema(
        tags=["User Goals"],
        request_body=UserGoalSerializer,
        operation_id='user-goals-update',
        operation_description="Update authenticated user's goal, rating, or course-completion final flag.",
    )
    def patch(self, request, goal_id):
        try:
            UserGoalListCreateApiView.expire_old_first_goals(request.user)
            goal = self.get_object(request, goal_id)
            if goal is None:
                self.response_format['status_code'] = status.HTTP_404_NOT_FOUND
                self.response_format["status"] = False
                self.response_format["message"] = _record_not_found
                return Response(self.response_format, status=status.HTTP_404_NOT_FOUND)

            serializer = self.serializer_class(
                goal,
                data=request.data,
                partial=True,
                context={'request': request},
            )
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            goal = serializer.save()
            goals = UserGoal.objects.filter(user=request.user).order_by('created_at', 'id')
            UserGoalListCreateApiView.build_goal_response(
                self.response_format,
                goals,
                status.HTTP_200_OK,
            )
            return Response(self.response_format, status=status.HTTP_200_OK)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})
