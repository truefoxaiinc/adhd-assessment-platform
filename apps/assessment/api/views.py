from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_token_user_or_none
from helpers.response import ResponseInfo
from helpers.exceptions.exceptions import safe_exception_response
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import APIException, ValidationError
from helpers.custom_messages import _success
import  os,sys
import logging

logger = logging.getLogger(__name__)
from django.db.models import Count, Q
from drf_yasg import openapi
from rest_framework.pagination import PageNumberPagination
from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResponse, SelfAssessmentResult
from apps.progresstracker.models import FaceAttentionSession
from apps.progresstracker.schemas import FaceAttentionSessionSchema
from apps.assessment.selectors import get_active_questions_for_user_type
from helpers.custom_messages import _success,_record_not_found
from apps.assessment.services.scoring_service import ScoringService
from apps.assessment.schemas import (
    SelfAssessmentQuestionsListSchema,SelfAssessmentResultSchema
)
from .serializers import (
    SelfAssessmentResponseSerializer
)
from apps.assessment.cache import (
    cache_get,
    cache_set,
    get_progress_cache_key,
    get_questions_cache_key,
    get_result_cache_key,
    get_score_list_cache_key,
)


class AssessmentScorePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    max_page_size = 100


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
                    'program_duration',
                )
                .filter(user=user_instance)
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
        


class AssessmentScoreListApiView(generics.GenericAPIView):
    serializer_class = FaceAttentionSessionSchema
    permission_classes = (IsAuthenticated,)
    pagination_class = AssessmentScorePagination

    SORT_FIELDS = {
        'id': 'id',
        'score': 'average_concentration_score',
        'attention_score': 'average_concentration_score',
        'engagement': 'attention_engagement_rate',
        'duration': 'session_duration_seconds',
        'created_at': 'created_at',
    }

    def get_queryset(self):
        queryset = (
            FaceAttentionSession.objects
            .filter(user_id=self.request.user.id)
            .only(
                'id',
                'user_id',
                'session_id',
                'is_assessment',
                'concentration_score',
                'gaze_ratio_avg',
                'inattention_duration',
                'drowsy_state',
                'face_detected',
                'video_attentive',
                'eyes_closed',
                'yawning',
                'gaze_state',
                'head_pose_ok',
                'low_light',
                'brightness_score',
                'pitch',
                'yaw',
                'roll',
                'blink_ratio',
                'yawn_distance',
                'attention_engagement_rate',
                'total_processed_frames',
                'sampled_frames',
                'average_confidence',
                'average_concentration_score',
                'bad_frame_count',
                'blurry_frame_count',
                'low_light_frame_count',
                'eyes_closed_count',
                'gaze_warning_count',
                'session_duration_seconds',
                'created_at',
            )
        )

        search = self.request.query_params.get('search', '').strip()
        gaze_state = self.request.query_params.get('gaze_state', '').strip()
        min_score = self.request.query_params.get('min_score')
        max_score = self.request.query_params.get('max_score')

        if search:
            search_query = (
                Q(session_id__icontains=search)
                | Q(gaze_state__icontains=search)
            )
            try:
                numeric_search = float(search)
            except (TypeError, ValueError):
                pass
            else:
                search_query |= Q(
                    average_concentration_score=numeric_search
                )
            queryset = queryset.filter(search_query)

        if gaze_state:
            queryset = queryset.filter(gaze_state__iexact=gaze_state)

        for field in (
            'is_assessment',
            'face_detected',
            'yawning',
            'eyes_closed',
            'low_light',
        ):
            value = self.request.query_params.get(field)
            if value in (None, ''):
                continue
            normalized_value = value.lower()
            if normalized_value not in ('true', 'false', '1', '0'):
                raise ValidationError({
                    field: 'Use true, false, 1, or 0.'
                })
            queryset = queryset.filter(
                **{field: normalized_value in ('true', '1')}
            )

        try:
            parsed_min_score = None
            parsed_max_score = None
            if min_score not in (None, ''):
                parsed_min_score = float(min_score)
                queryset = queryset.filter(
                    average_concentration_score__gte=parsed_min_score
                )
            if max_score not in (None, ''):
                parsed_max_score = float(max_score)
                queryset = queryset.filter(
                    average_concentration_score__lte=parsed_max_score
                )
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {'score': 'min_score and max_score must be valid numbers.'}
            ) from exc
        if (
            parsed_min_score is not None
            and parsed_max_score is not None
            and parsed_min_score > parsed_max_score
        ):
            raise ValidationError({
                'score': 'min_score cannot be greater than max_score.'
            })

        requested_sort = (
            self.request.query_params.get('sort')
            or self.request.query_params.get('ordering')
            or '-created_at'
        )
        descending = requested_sort.startswith('-')
        sort_name = requested_sort.lstrip('-')
        sort_field = self.SORT_FIELDS.get(sort_name)
        if sort_field is None:
            raise ValidationError({
                'sort': (
                    'Invalid sort field. Use id, score, attention_score, '
                    'engagement, duration, or created_at.'
                )
            })

        ordering = f'-{sort_field}' if descending else sort_field
        if sort_field == 'id':
            return queryset.order_by(ordering)
        return queryset.order_by(ordering, '-id')

    @swagger_auto_schema(
        tags=["AI Attention Assessment"],
        operation_id='authenticated-user-ai-attention-score-list',
        operation_description=(
            "List the authenticated user's AI attention sessions with pagination, "
            "search, filters, sorting, and cache-backed responses. Score filters "
            "use the raw 0-8 concentration scale."
        ),
        manual_parameters=[
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('limit', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('search', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('gaze_state', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('is_assessment', openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('face_detected', openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('yawning', openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('eyes_closed', openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('low_light', openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('min_score', openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter('max_score', openapi.IN_QUERY, type=openapi.TYPE_NUMBER),
            openapi.Parameter(
                'sort',
                openapi.IN_QUERY,
                description=(
                    'id, score, attention_score, engagement, duration, or created_at; '
                    'prefix with - for descending.'
                ),
                type=openapi.TYPE_STRING,
            ),
        ],
    )
    def get(self, request):
        try:
            cache_key = get_score_list_cache_key(request.user.id, request)
            cached_data = cache_get(cache_key)
            if cached_data is not None:
                return Response(cached_data, status=status.HTTP_200_OK)

            summary = FaceAttentionSession.objects.filter(
                user_id=request.user.id
            ).aggregate(
                total_sessions=Count('id'),
                total_assessments=Count(
                    'id',
                    filter=Q(is_assessment=True),
                ),
                total_management=Count(
                    'id',
                    filter=Q(is_assessment=False),
                ),
            )

            page = self.paginate_queryset(self.get_queryset())
            data = self.serializer_class(
                page,
                many=True,
                context={'request': request},
            ).data
            response_data = {
                'status_code': status.HTTP_200_OK,
                'status': True,
                'message': _success,
                'data': {
                    'count': self.paginator.page.paginator.count,
                    'total_sessions': summary['total_sessions'],
                    'total_assessments': summary['total_assessments'],
                    'total_management': summary['total_management'],
                    'next': self.paginator.get_next_link(),
                    'previous': self.paginator.get_previous_link(),
                    'results': data,
                },
            }
            cache_set(cache_key, response_data)
            return Response(response_data, status=status.HTTP_200_OK)
        except APIException:
            raise
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
