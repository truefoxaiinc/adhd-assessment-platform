from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_token_user_or_none
from helpers.response import ResponseInfo
from helpers.exceptions.exceptions import safe_exception_response
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
from helpers.custom_messages import _success
import  os,sys
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from math import ceil

logger = logging.getLogger(__name__)
from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResponse, SelfAssessmentResult
from apps.assessment.selectors import get_active_questions_for_user_type
from helpers.custom_messages import _success,_record_not_found
from apps.assessment.services.scoring_service import ScoringService
from apps.assessment.services.assessment_service import AssessmentService
from apps.assessment.schemas import (
    AIAssessmentScoreSchema, SelfAssessmentQuestionsListSchema,
    SelfAssessmentResultSchema,
)
from apps.progresstracker.models import FaceAttentionSession, ManagementActivitySession
from django.utils import timezone
from .serializers import (
    FrontendAttentionScoreSerializer,
    ManagementActivityScoreSerializer,
    SelfAssessmentResponseSerializer
)
from apps.assessment.cache import (
    bump_user_result_cache,
    cache_get,
    cache_set,
    get_management_week_details_cache_key,
    get_progress_cache_key,
    get_questions_cache_key,
    get_result_cache_key,
)


class GetSelfAssessmentQuestionsListApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(GetSelfAssessmentQuestionsListApiView, self).__init__(**kwargs)

    serializer_class    = SelfAssessmentQuestionsListSchema
    permission_classes  = (IsAuthenticated,)
    filter_backends     = []

    @swagger_auto_schema(tags=["Self Assessment"],operation_id='Self Assessment Questions Fetch',operation_description="This API used to fetch the questions that used for the Self assessment section",)
    def get(self, request):

        try:
            user_instance   = get_token_user_or_none(request)
            is_for_adults   = bool(user_instance.adult)

            cache_key = get_questions_cache_key(request, is_for_adults)
            cached_data = cache_get(cache_key)
            if cached_data:
                return Response(cached_data, status=status.HTTP_200_OK)

            queryset = get_active_questions_for_user_type(is_for_adults)
            data = self.serializer_class(queryset, many=True, context={'request': request}).data

            final_data = {"questions": data}

            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["status"] = True
            self.response_format["message"] = _success
            self.response_format["data"] = final_data
            
            cache_set(cache_key, self.response_format)
            return Response(self.response_format, status=status.HTTP_200_OK)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})
        

class SelfAssessmentResponseApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(SelfAssessmentResponseApiView, self).__init__(**kwargs)

    serializer_class = SelfAssessmentResponseSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(tags=["Self Assessment"],operation_id='Self Assessment Save',operation_description="This API used to save the response for the self assessment questionaire",)
    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data, context = {'request' : request})
            if not serializer.is_valid():
                self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                self.response_format["status"] = False
                self.response_format["errors"] = serializer.errors
                return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

            instance = serializer.save()

            bump_user_result_cache(instance.user_id)

            data = SelfAssessmentResultSchema(instance, context={'request': request}).data

            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["message"] = _success
            self.response_format["status"] = True
            self.response_format["data"] = data
            return Response(self.response_format, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            self.response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            self.response_format["status"] = False
            self.response_format["errors"] = e.detail
            self.response_format["message"] = "Validation Error"
            return Response(self.response_format, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class ResultFetchApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(ResultFetchApiView, self).__init__(**kwargs)

    serializer_class    = SelfAssessmentResultSchema
    permission_classes  = (IsAuthenticated,)
    filter_backends     = []

    @swagger_auto_schema(tags=["Self Assessment"],operation_id='Self Assessment Result Fetch',operation_description="This API used to fetch the last self assessment result of the current user",)
    def get(self, request):

        try:
            user_instance   = get_token_user_or_none(request)
            is_for_adults = bool(user_instance.adult)
            
            cache_key = get_result_cache_key(user_instance.id)
            cached_data = cache_get(cache_key)
            if cached_data:
                cached_result = cached_data.get("data") or {}
                if cached_result.get("is_completed") is True or cached_result.get("completed_at"):
                    return Response(cached_data, status=status.HTTP_200_OK)

            latest_result = (
                SelfAssessmentResult.objects
                .filter(user=user_instance)
                .order_by('-id')
                .first()
            )
            if latest_result and latest_result.completed_at is None:
                was_incomplete = latest_result.completed_at is None
                latest_result = AssessmentService.calculate_result(
                    latest_result,
                    is_for_adults,
                )
                if was_incomplete and latest_result.completed_at is not None:
                    bump_user_result_cache(user_instance.id)

            instance = (
                SelfAssessmentResult.objects
                .select_related('user')
                .only(
                    'id',
                    'user_id',
                    'user__username',
                    'result',
                    'raw_total',
                    'tenscore',
                    'read_focus_total',
                    'visual_tracking_total',
                    'audio_listening_total',
                    'created_at',
                    'completed_at',
                )
                .filter(user=user_instance)
                .filter(completed_at__isnull=False)
                .order_by('-id')
                .first()
            )
            if instance is not None:
                data = SelfAssessmentResultSchema(instance, context={'request': request}).data
            else:
                completion = {
                    "total_questions": 0,
                    "answered_questions": 0,
                    "pending_questions": 0,
                    "completed_percentage": 0,
                }
                if latest_result is not None:
                    completion = AssessmentService.get_completion_summary(
                        latest_result,
                        is_for_adults,
                    )
                    data = SelfAssessmentResultSchema(
                        latest_result,
                        context={'request': request},
                    ).data
                else:
                    data = {
                        "id": "",
                        "user": user_instance.username or "",
                        "result": "",
                        "raw_total": "",
                        "tenscore": "",
                        "read_focus_total": "",
                        "visual_tracking_total": "",
                        "audio_listening_total": "",
                        "is_completed": False,
                        "created_at": "",
                        "completed_at": "",
                    }
                data.update({
                    "total_questions": completion["total_questions"],
                    "answered_questions": completion["answered_questions"],
                    "pending_questions": completion["pending_questions"],
                    "completed_percentage": completion["completed_percentage"],
                })

            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["message"] = _success
            self.response_format["status"] = True
            self.response_format["data"] = data
            
            if data.get("is_completed") is True:
                cache_set(cache_key, self.response_format)
            return Response(self.response_format, status=status.HTTP_200_OK)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class ResultHistoryApiView(generics.GenericAPIView):
    """List every completed assessment attempt for the authenticated user."""

    serializer_class = SelfAssessmentResultSchema
    permission_classes = (IsAuthenticated,)
    filter_backends = []

    @swagger_auto_schema(
        tags=["Self Assessment"],
        operation_id='Self Assessment Result History',
        operation_description="Fetch all completed self-assessment scores for the authenticated user, newest first.",
    )
    def get(self, request):
        try:
            user_instance = get_token_user_or_none(request)
            queryset = (
                SelfAssessmentResult.objects
                .select_related('user')
                .filter(user=user_instance, completed_at__isnull=False)
                .order_by('-completed_at', '-id')
            )
            data = self.serializer_class(
                queryset,
                many=True,
                context={'request': request},
            ).data

            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_200_OK
            response_format["message"] = _success
            response_format["status"] = True
            response_format["data"] = {
                "count": len(data),
                "results": data,
            }
            return Response(response_format, status=status.HTTP_200_OK)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class AIAssessmentScoreHistoryApiView(generics.GenericAPIView):
    serializer_class = AIAssessmentScoreSchema
    permission_classes = (IsAuthenticated,)
    filter_backends = []

    @swagger_auto_schema(
        tags=["AI Assessment"],
        operation_id='AI Assessment Score History',
        operation_description=(
            "List the authenticated user's AI attention scores. Filter with "
            "is_assessment=true for assessments or is_assessment=false for "
            "regular management sessions."
        ),
    )
    def get(self, request):
        try:
            is_assessment = request.query_params.get('is_assessment')
            user_id = int(request.user.id)
            queryset = FaceAttentionSession.objects.filter(
                user_id=user_id
            ).order_by('-created_at', '-id')

            if is_assessment not in (None, ''):
                normalized_value = str(is_assessment).strip().lower()
                if normalized_value not in ('true', 'false'):
                    raise ValidationError({
                        'is_assessment': 'Use true or false.'
                    })
                queryset = queryset.filter(
                    is_assessment=normalized_value == 'true'
                )

            data = self.serializer_class(queryset, many=True).data
            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_200_OK
            response_format["message"] = _success
            response_format["status"] = True
            response_format["data"] = {
                "count": len(data),
                "results": data,
            }
            return Response(response_format, status=status.HTTP_200_OK)
        except ValidationError as e:
            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            response_format["status"] = False
            response_format["message"] = "Validation Error"
            response_format["errors"] = e.detail
            return Response(response_format, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class FrontendAttentionScoreSaveApiView(generics.GenericAPIView):
    serializer_class = FrontendAttentionScoreSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=["AI Assessment"],
        operation_id='Save Frontend Attention Score',
        operation_description=(
            "Save final attention/detection metrics calculated on the frontend "
            "after video completion. Backend only stores the submitted result."
        ),
        request_body=FrontendAttentionScoreSerializer,
    )
    def post(self, request):
        try:
            serializer = self.serializer_class(
                data=request.data,
                context={'request': request},
            )
            if not serializer.is_valid():
                response_format = ResponseInfo().response
                response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                response_format["status"] = False
                response_format["message"] = "Validation Error"
                response_format["errors"] = serializer.errors
                return Response(response_format, status=status.HTTP_400_BAD_REQUEST)

            instance = serializer.save()
            data = AIAssessmentScoreSchema(instance).data

            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_201_CREATED
            response_format["message"] = _success
            response_format["status"] = True
            response_format["data"] = data
            return Response(response_format, status=status.HTTP_201_CREATED)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class ManagementActivityScoreSaveApiView(generics.GenericAPIView):
    serializer_class = ManagementActivityScoreSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        tags=["Management"],
        operation_id='Save Management Activity Score',
        operation_description=(
            "Save frontend-generated management activity telemetry. "
            "The authenticated JWT user owns the saved score."
        ),
        request_body=ManagementActivityScoreSerializer,
    )
    def post(self, request):
        try:
            serializer = self.serializer_class(
                data=request.data,
                context={'request': request},
            )
            if not serializer.is_valid():
                response_format = ResponseInfo().response
                response_format['status_code'] = status.HTTP_400_BAD_REQUEST
                response_format["status"] = False
                response_format["message"] = "Validation Error"
                response_format["errors"] = serializer.errors
                return Response(response_format, status=status.HTTP_400_BAD_REQUEST)

            instance = serializer.save()

            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_201_CREATED
            response_format["message"] = _success
            response_format["status"] = True
            response_format["data"] = self.serializer_class(instance).data
            return Response(response_format, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            response_format["status"] = False
            response_format["message"] = "Validation Error"
            response_format["errors"] = e.detail
            return Response(response_format, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})


class ManagementDashboardApiView(generics.GenericAPIView):
    serializer_class = serializers.Serializer
    permission_classes = (IsAuthenticated,)
    filter_backends = []

    @swagger_auto_schema(
        tags=["Management"],
        operation_id='Management Dashboard',
        operation_description=(
            "Fetch authenticated user's management dashboard overview, "
            "weekly score trend, and latest week day details."
        ),
    )
    def get(self, request):
        try:
            weeks_count = self._get_weeks_count(request)
            sessions = self._get_user_management_sessions(request.user)
            data = self._build_dashboard_data(sessions, weeks_count)

            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_200_OK
            response_format["message"] = _success
            response_format["status"] = True
            response_format["data"] = data
            return Response(response_format, status=status.HTTP_200_OK)
        except ValidationError as e:
            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            response_format["status"] = False
            response_format["message"] = "Validation Error"
            response_format["errors"] = e.detail
            return Response(response_format, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})

    @staticmethod
    def _get_weeks_count(request):
        weeks_param = request.query_params.get('weeks', 6)
        try:
            weeks_count = int(weeks_param)
        except (TypeError, ValueError):
            raise ValidationError({'weeks': 'Use a number between 1 and 52.'})

        if weeks_count < 1 or weeks_count > 52:
            raise ValidationError({'weeks': 'Use a number between 1 and 52.'})

        return weeks_count

    @staticmethod
    def _get_user_management_sessions(user):
        return list(
            FaceAttentionSession.objects
            .filter(user=user, is_assessment=False)
            .select_related('file')
            .order_by('created_at', 'id')
        )

    @staticmethod
    def _get_user_management_activity_sessions(user):
        return list(
            ManagementActivitySession.objects
            .filter(user=user, is_assessment=False)
            .select_related('content')
            .order_by('created_at', 'id')
        )

    @classmethod
    def _build_dashboard_data(cls, sessions, weeks_count):
        week_buckets = defaultdict(list)

        for session in sessions:
            session_date = timezone.localtime(session.created_at).date()
            week_start = session_date - timedelta(days=session_date.weekday())
            week_buckets[week_start].append(session)

        week_starts = sorted(week_buckets.keys())
        selected_week_starts = week_starts[-weeks_count:]
        weekly_progress = [
            cls._serialize_week(week_start, week_buckets[week_start], index + 1)
            for index, week_start in enumerate(selected_week_starts)
        ]

        all_scores = [cls._session_score(session) for session in sessions]
        weekly_scores = [
            cls._average([cls._session_score(session) for session in week_buckets[week_start]])
            for week_start in week_starts
        ]

        improvement = cls._build_improvement(weekly_progress)

        return {
            "overview": {
                "weeks_tracked": len(week_starts),
                "average_total_score": cls._average(all_scores),
                "best_week_score": round(max(weekly_scores), 2) if weekly_scores else 0,
                "consistency_percentage": cls._consistency_percentage(sessions),
            },
            "weekly_progress": {
                "metric": "total_score",
                "range_weeks": weeks_count,
                "results": weekly_progress,
                "improvement": improvement,
            },
        }

    @classmethod
    def _build_all_week_details(cls, sessions, selected_date=None, activity_sessions=None):
        activity_sessions = activity_sessions or []
        week_buckets = defaultdict(list)
        day_buckets = defaultdict(list)

        for session in sessions:
            session_date = timezone.localtime(session.created_at).date()
            week_start = session_date - timedelta(days=session_date.weekday())
            week_buckets[week_start].append(session)
            day_buckets[session_date].append(session)

        for session in activity_sessions:
            session_date = timezone.localtime(session.started_at).date()
            week_start = session_date - timedelta(days=session_date.weekday())
            week_buckets[week_start].append(session)
            day_buckets[session_date].append(session)

        return [
            cls._serialize_week_details(
                week_start,
                day_buckets,
                selected_week_number=index + 1,
                selected_date=selected_date,
            )
            for index, week_start in enumerate(sorted(week_buckets.keys()))
        ]

    @staticmethod
    def _get_selected_date(request):
        selected_date = request.query_params.get('selected_date') or request.query_params.get('date')
        if not selected_date:
            return None
        try:
            return datetime.strptime(selected_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            raise ValidationError({'selected_date': 'Use date format YYYY-MM-DD.'})

    @staticmethod
    def _get_pagination_params(request):
        try:
            page = int(request.query_params.get('page', 1))
            limit = int(request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            raise ValidationError({
                'pagination': 'Use numeric page and limit values.'
            })

        if page < 1:
            raise ValidationError({'page': 'Use a number greater than or equal to 1.'})
        if limit < 1 or limit > 52:
            raise ValidationError({'limit': 'Use a number between 1 and 52.'})

        return page, limit

    @classmethod
    def _paginate_week_details(cls, request, results, page, limit):
        count = len(results)
        total_pages = ceil(count / limit) if count else 0
        start = (page - 1) * limit
        end = start + limit

        return {
            "links": {
                "next": cls._page_link(request, page + 1, total_pages),
                "previous": cls._page_link(request, page - 1, total_pages),
            },
            "count": count,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "results": results[start:end],
        }

    @staticmethod
    def _page_link(request, page_number, total_pages):
        if page_number < 1 or page_number > total_pages:
            return ""

        query_params = request.query_params.copy()
        query_params['page'] = page_number
        return f"{request.path}?{query_params.urlencode()}"

    @staticmethod
    def _session_score(session):
        if isinstance(session, ManagementActivitySession):
            return round(session.final_score, 2)
        return round((session.average_concentration_score / 8.0) * 100, 2)

    @classmethod
    def _serialize_week(cls, week_start, sessions, week_number):
        scores = [cls._session_score(session) for session in sessions]
        return {
            "week_number": week_number,
            "label": f"Wk {week_number}",
            "start_date": week_start.isoformat(),
            "end_date": (week_start + timedelta(days=6)).isoformat(),
            "total_score": cls._average(scores),
        }

    @classmethod
    def _serialize_week_details(cls, week_start, day_buckets, selected_week_number, selected_date=None):
        days = []
        for day_offset in range(7):
            day = week_start + timedelta(days=day_offset)
            sessions = day_buckets.get(day, [])
            day_summary = cls._serialize_day(day, sessions)
            days.append(day_summary)

        selected_day = None
        if selected_date and week_start <= selected_date <= week_start + timedelta(days=6):
            selected_day = next((day for day in days if day["date"] == selected_date.isoformat()), None)
        if selected_day is None:
            selected_day = next((day for day in days if day["has_data"]), None)
        if selected_day is None:
            selected_day = days[0] if days else None

        return {
            "week_number": selected_week_number,
            "start_date": week_start.isoformat(),
            "end_date": (week_start + timedelta(days=6)).isoformat(),
            "days": days,
            "selected_day": selected_day,
        }

    @classmethod
    def _serialize_day(cls, day, sessions):
        scores = [cls._session_score(session) for session in sessions]
        total_score = cls._average(scores)

        return {
            "date": day.isoformat(),
            "day_label": day.strftime("%a"),
            "day_number": day.day,
            "has_data": bool(sessions),
            "status_label": cls._day_status(total_score) if sessions else "",
            "sessions_count": len(sessions),
            "sessions": [
                cls._serialize_management_session(session)
                for session in sorted(
                    sessions,
                    key=lambda item: (cls._session_started_at(item), item.id),
                )
            ],
        }

    @classmethod
    def _serialize_management_session(cls, session):
        if isinstance(session, ManagementActivitySession):
            return cls._serialize_activity_session(session)
        return cls._serialize_session(session)

    @staticmethod
    def _session_started_at(session):
        if isinstance(session, ManagementActivitySession):
            return session.started_at
        return session.created_at

    @classmethod
    def _serialize_activity_session(cls, session):
        local_started_at = timezone.localtime(session.started_at)
        local_completed_at = timezone.localtime(session.completed_at) if session.completed_at else None
        content = session.content

        return {
            "id": session.id,
            "user_id": session.user_id,
            "file": content.id if content else None,
            "session_id": "",
            "file_id": content.id if content else None,
            "file_title": content.title if content else session.activity_code.replace('_', ' ').title(),
            "content_type": session.content_type,
            "content_label": "ACTIVITY",
            "activity_code": session.activity_code,
            "management_day": session.management_day,
            "is_assessment": session.is_assessment,
            "status": session.status,
            "level": session.level,
            "difficulty": session.difficulty,
            "score": round(session.final_score, 2),
            "final_score": round(session.final_score, 2),
            "target_count": session.target_count,
            "completed_count": session.completed_count,
            "correct_count": session.correct_count,
            "incorrect_count": session.incorrect_count,
            "missed_count": session.missed_count,
            "assisted_count": session.assisted_count,
            "action_count": session.action_count,
            "average_response_time_ms": round(session.average_response_time_ms, 2),
            "accuracy_rate": round(session.accuracy_rate, 2),
            "completion_rate": round(session.completion_rate, 2),
            "response_control_score": round(session.response_control_score, 2),
            "speed_score": round(session.speed_score, 2),
            "attention_score": round(session.attention_score, 2),
            "performance_score": round(session.performance_score, 2),
            "started_at": local_started_at.isoformat(),
            "completed_at": local_completed_at.isoformat() if local_completed_at else "",
            "created_at": timezone.localtime(session.created_at).isoformat(),
            "time_label": local_started_at.strftime("%I:%M %p").lstrip("0"),
            "session_duration_seconds": round(session.session_duration_seconds, 2),
            "duration_seconds": round(session.session_duration_seconds, 2),
            "duration_label": cls._format_duration(session.session_duration_seconds),
        }

    @classmethod
    def _serialize_session(cls, session):
        local_created_at = timezone.localtime(session.created_at)
        content = session.file
        content_type = session.content_type or (content.file_type if content else "")
        score = session.final_score or cls._session_score(session)

        return {
            "id": session.id,
            "user_id": session.user_id,
            "file": content.id if content else None,
            "session_id": session.session_id,
            "file_id": content.id if content else None,
            "file_title": content.title if content else "",
            "content_type": content_type,
            "content_label": content_type.upper() if content_type else "",
            "is_assessment": session.is_assessment,
            "calculation_version": session.calculation_version,
            "score": round(score, 2),
            "final_score": round(session.final_score, 2),
            "concentration_score": round(session.concentration_score, 2),
            "gaze_ratio_avg": round(session.gaze_ratio_avg, 4),
            "inattention_duration": round(session.inattention_duration, 2),
            "maximum_inattention_duration": round(session.maximum_inattention_duration, 2),
            "drowsy_state": round(session.drowsy_state, 4),
            "brightness_score": round(session.brightness_score, 2),
            "pitch": round(session.pitch, 2),
            "yaw": round(session.yaw, 2),
            "roll": round(session.roll, 2),
            "blink_ratio": round(session.blink_ratio, 4),
            "yawn_distance": round(session.yawn_distance, 4),
            "attention_engagement_rate": round(session.attention_engagement_rate, 2),
            "reading_engagement_rate": round(session.reading_engagement_rate, 2),
            "total_processed_frames": session.total_processed_frames,
            "sampled_frames": session.sampled_frames,
            "reading_focused_frames": session.reading_focused_frames,
            "watching_video_frames": session.watching_video_frames,
            "idle_distracted_frames": session.idle_distracted_frames,
            "average_confidence": round(session.average_confidence, 4),
            "average_concentration_score": round(session.average_concentration_score, 2),
            "gaze_quality_avg": round(session.gaze_quality_avg, 4),
            "reading_gaze_frequency_avg_hz": round(session.reading_gaze_frequency_avg_hz, 4),
            "reading_gaze_amplitude_avg": round(session.reading_gaze_amplitude_avg, 4),
            "bad_frame_count": session.bad_frame_count,
            "blurry_frame_count": session.blurry_frame_count,
            "low_light_frame_count": session.low_light_frame_count,
            "eyes_closed_count": session.eyes_closed_count,
            "gaze_warning_count": session.gaze_warning_count,
            "session_duration_seconds": round(session.session_duration_seconds, 2),
            "created_at": local_created_at.isoformat(),
            "started_at": local_created_at.isoformat(),
            "time_label": local_created_at.strftime("%I:%M %p").lstrip("0"),
            "duration_seconds": round(session.session_duration_seconds, 2),
            "duration_label": cls._format_duration(session.session_duration_seconds),
        }

    @staticmethod
    def _average(values):
        if not values:
            return 0
        return round(sum(values) / len(values), 2)

    @staticmethod
    def _consistency_percentage(sessions):
        if not sessions:
            return 0

        session_dates = {
            timezone.localtime(session.created_at).date()
            for session in sessions
        }
        first_date = min(session_dates)
        last_date = max(session_dates)
        total_days = (last_date - first_date).days + 1
        if total_days <= 0:
            return 0
        return round((len(session_dates) / total_days) * 100, 2)

    @staticmethod
    def _build_improvement(weekly_progress):
        if len(weekly_progress) < 2:
            return {
                "points": 0,
                "from_week": None,
                "to_week": None,
            }

        first_week = weekly_progress[0]
        last_week = weekly_progress[-1]
        return {
            "points": round(last_week["total_score"] - first_week["total_score"], 2),
            "from_week": first_week["label"],
            "to_week": last_week["label"],
        }

    @staticmethod
    def _day_status(score):
        if score >= 80:
            return "Good Day"
        if score >= 50:
            return "Average Day"
        return "Needs Focus"

    @staticmethod
    def _format_duration(total_seconds):
        total_minutes = int(total_seconds // 60)
        hours, minutes = divmod(total_minutes, 60)
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"


class ManagementLatestWeekApiView(generics.GenericAPIView):
    serializer_class = serializers.Serializer
    permission_classes = (IsAuthenticated,)
    filter_backends = []

    @swagger_auto_schema(
        tags=["Management"],
        operation_id='Management Latest Week',
        operation_description=(
            "Fetch authenticated user's management week-by-week day details."
        ),
    )
    def get(self, request):
        try:
            page, limit = ManagementDashboardApiView._get_pagination_params(request)
            selected_date = ManagementDashboardApiView._get_selected_date(request)
            cache_key = get_management_week_details_cache_key(request.user.id, request)
            cached_response = cache_get(cache_key)
            if cached_response:
                return Response(cached_response, status=status.HTTP_200_OK)

            sessions = ManagementDashboardApiView._get_user_management_sessions(request.user)
            activity_sessions = ManagementDashboardApiView._get_user_management_activity_sessions(request.user)
            week_details = ManagementDashboardApiView._build_all_week_details(
                sessions,
                selected_date=selected_date,
                activity_sessions=activity_sessions,
            )
            paginated_week_details = ManagementDashboardApiView._paginate_week_details(
                request,
                week_details,
                page,
                limit,
            )

            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_200_OK
            response_format["message"] = _success
            response_format["status"] = True
            response_format["data"] = paginated_week_details
            cache_set(cache_key, response_format)
            return Response(response_format, status=status.HTTP_200_OK)
        except ValidationError as e:
            response_format = ResponseInfo().response
            response_format['status_code'] = status.HTTP_400_BAD_REQUEST
            response_format["status"] = False
            response_format["message"] = "Validation Error"
            response_format["errors"] = e.detail
            return Response(response_format, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return safe_exception_response(e, context={'view': self})
        


class SelfAssessmentProgressApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(SelfAssessmentProgressApiView, self).__init__(**kwargs)

    permission_classes = (IsAuthenticated,)
    serializer_class = SelfAssessmentQuestionsListSchema
    filter_backends = []

    @swagger_auto_schema(
        tags=["Self Assessment"],
        operation_id='Self Assessment Progress Fetch',
        operation_description="Fetch all active assessment questions with the current user's saved answers and pending/completed counts for mobile progress UI.",
    )
    def get(self, request):
        try:
            user_instance = get_token_user_or_none(request)
            is_for_adults = bool(user_instance.adult)

            requested_question_id = request.query_params.get('question_id')
            cache_key = get_progress_cache_key(user_instance.id, is_for_adults)
            if requested_question_id:
                cache_key += f"_{requested_question_id}"

            cached_data = cache_get(cache_key)
            if cached_data:
                return Response(cached_data, status=status.HTTP_200_OK)

            latest_result = (
                SelfAssessmentResult.objects
                .filter(user=user_instance, completed_at__isnull=True)
                .only('id', 'user_id')
                .order_by('-id')
                .first()
            )

            questions = list(
                SelfAssessmentQuestions.objects
                .filter(is_for_adults=is_for_adults, is_active=True)
                .only('id', 'question_text', 'category')
                .order_by('id')
            )

            response_map = {}
            if latest_result:
                responses = (
                    SelfAssessmentResponse.objects
                    .filter(result_entry=latest_result, question_id__in=[question.id for question in questions])
                    .only('id', 'question_id', 'response', 'text_response')
                )
                response_map = {response.question_id: response for response in responses}

            question_items = []
            answered_questions = 0

            requested_question_id = request.query_params.get('question_id')

            for index, question in enumerate(questions, start=1):
                saved_response = response_map.get(question.id)
                is_answered = saved_response is not None
                if is_answered:
                    answered_questions += 1

                if requested_question_id and str(question.id) != str(requested_question_id):
                    continue

                question_items.append({
                    'position': index,
                    'question_id': question.id,
                    'question_text': question.question_text or '',
                    'category': question.category or '',
                    'is_answered': is_answered,
                    'status': 'completed' if is_answered else 'pending',
                    'response_id': saved_response.id if saved_response else None,
                    'answer': saved_response.response if saved_response else '',
                    'text_response': saved_response.text_response if saved_response else '',
                })

            total_questions = len(questions)
            pending_questions = total_questions - answered_questions
            completed_percentage = round((answered_questions / total_questions) * 100, 2) if total_questions else 0

            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["status"] = True
            self.response_format["message"] = _success
            self.response_format["data"] = {
                'result_id': latest_result.id if latest_result else None,
                'total_questions': total_questions,
                'answered_questions': answered_questions,
                'pending_questions': pending_questions,
                'completed_percentage': completed_percentage,
                'questions': question_items,
            }

            cache_set(cache_key, self.response_format)
            return Response(self.response_format, status=status.HTTP_200_OK)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})




























class TestApiView(generics.GenericAPIView):
    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(TestApiView, self).__init__(**kwargs)

    serializer_class = SelfAssessmentResponseSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(tags=["Self Assessment"],operation_id='Test',operation_description="This API used to Test backend Algorithm",)
    def post(self, request):
        try:

            is_adult = False
            user_instance = get_token_user_or_none(request)
            instance = SelfAssessmentResult.objects.filter(user=user_instance).first()
            ScoringService.calculate_self_assessment(instance, is_adult)

            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["message"] = _success
            self.response_format["status"] = True
            return Response(self.response_format, status=status.HTTP_201_CREATED)

        except Exception as e:
            return safe_exception_response(e, context={'view': self})
