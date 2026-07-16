from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_token_user_or_none
from helpers.response import ResponseInfo
from helpers.exceptions.exceptions import safe_exception_response
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from helpers.custom_messages import _success
import  os,sys
import logging
from collections import defaultdict
from datetime import timedelta
from math import ceil

logger = logging.getLogger(__name__)
from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResponse, SelfAssessmentResult
from apps.assessment.selectors import get_active_questions_for_user_type
from helpers.custom_messages import _success,_record_not_found
from apps.assessment.services.scoring_service import ScoringService
from apps.assessment.schemas import (
    AIAssessmentScoreSchema, SelfAssessmentQuestionsListSchema,
    SelfAssessmentResultSchema,
)
from apps.progresstracker.models import FaceAttentionSession
from django.utils import timezone
from .serializers import (
    FrontendAttentionScoreSerializer,
    SelfAssessmentResponseSerializer
)
from apps.assessment.cache import (
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

            from apps.assessment.cache import bump_user_result_cache
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
            
            cache_key = get_result_cache_key(user_instance.id)
            cached_data = cache_get(cache_key)
            if cached_data:
                return Response(cached_data, status=status.HTTP_200_OK)

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
                )
                .filter(user=user_instance)
                .filter(completed_at__isnull=False)
                .order_by('-id')
                .first()
            )
            data            = SelfAssessmentResultSchema(instance, context={'request': request}).data

            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["message"] = _success
            self.response_format["status"] = True
            self.response_format["data"] = data
            
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


class ManagementDashboardApiView(generics.GenericAPIView):
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
    def _build_all_week_details(cls, sessions):
        week_buckets = defaultdict(list)
        day_buckets = defaultdict(list)

        for session in sessions:
            session_date = timezone.localtime(session.created_at).date()
            week_start = session_date - timedelta(days=session_date.weekday())
            week_buckets[week_start].append(session)
            day_buckets[session_date].append(session)

        return [
            cls._serialize_week_details(
                week_start,
                day_buckets,
                selected_week_number=index + 1,
            )
            for index, week_start in enumerate(sorted(week_buckets.keys()))
        ]

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
    def _serialize_week_details(cls, week_start, day_buckets, selected_week_number):
        days = []
        for day_offset in range(7):
            day = week_start + timedelta(days=day_offset)
            sessions = day_buckets.get(day, [])
            day_summary = cls._serialize_day(day, sessions)
            days.append(day_summary)

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
        concentration_scores = [
            round((session.concentration_score / 8.0) * 100, 2)
            for session in sessions
        ]
        attention_scores = [session.attention_engagement_rate for session in sessions]
        duration_seconds = sum(session.session_duration_seconds for session in sessions)
        total_score = cls._average(scores)

        return {
            "date": day.isoformat(),
            "day_label": day.strftime("%a"),
            "day_number": day.day,
            "has_data": bool(sessions),
            "status_label": cls._day_status(total_score) if sessions else "",
            "total_score": total_score,
            "concentration_score": cls._average(concentration_scores),
            "attention_score": cls._average(attention_scores),
            "duration_seconds": round(duration_seconds, 2),
            "duration_label": cls._format_duration(duration_seconds),
            "sessions_count": len(sessions),
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
            cache_key = get_management_week_details_cache_key(request.user.id, request)
            cached_response = cache_get(cache_key)
            if cached_response:
                return Response(cached_response, status=status.HTTP_200_OK)

            sessions = ManagementDashboardApiView._get_user_management_sessions(request.user)
            week_details = ManagementDashboardApiView._build_all_week_details(sessions)
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
                .filter(user=user_instance)
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
