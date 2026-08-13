from django.db.models import Count, Exists, Max, OuterRef, Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.filehandler.learning_serializers import (
    ContentAnswerResultSerializer,
    ContentAttemptSerializer,
    PublicContentQuestionSerializer,
    StartAttemptSerializer,
    SubmitAttemptSerializer,
)
from apps.filehandler.learning_services import LearningContentService
from apps.filehandler.models import AdhdContent, AttemptStatus, ContentAttempt, ContentStatus
from apps.payments.selectors import user_has_active_subscription
from helpers.response import ResponseInfo


def api_response(*, data=None, message='Success', status_code=status.HTTP_200_OK, errors=None):
    payload = ResponseInfo(
        status=200 <= status_code < 300,
        status_code=status_code,
        message=message,
        data=data if data is not None else {},
        errors=errors if errors is not None else {},
    ).response
    return Response(payload, status=status_code)


class ContentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class LearningContentMixin:
    permission_classes = [IsAuthenticated]

    @staticmethod
    def section_is_management(section):
        normalized = (section or '').strip().lower()
        if normalized not in ('management', 'assessment'):
            raise ValidationError({'section': 'Use management or assessment.'})
        return normalized == 'management'

    @staticmethod
    def absolute_url(request, file_field):
        if not file_field:
            return None
        return request.build_absolute_uri(file_field.url)

    def serialize_content(self, content, request, unlocked_days, completed_ids):
        is_locked = LearningContentService.is_locked(content, request.user, unlocked_days)
        return {
            'id': content.id,
            'title': content.title,
            'description': content.description,
            'content_type': content.file_type,
            'section': 'management' if content.is_management else 'assessment',
            'day': content.day,
            'display_order': content.order_number,
            'age_group': content.age_group,
            'estimated_duration_minutes': content.estimated_duration_minutes,
            'cover_image_url': self.absolute_url(request, content.cover_image),
            'thumbnail_url': self.absolute_url(request, content.cover_image),
            'activity_code': content.activity_name,
            'has_questions': content.question_count > 0,
            'question_count': content.question_count,
            'question_mode': content.question_mode if content.question_count else None,
            'is_locked': is_locked,
            'locked_reason': LearningContentService.locked_reason(content, request.user, unlocked_days),
            'is_completed': content.id in completed_ids,
            'completed_at': content.completed_at,
        }


class LearningContentListApiView(LearningContentMixin, generics.GenericAPIView):
    serializer_class = StartAttemptSerializer
    pagination_class = ContentPagination

    @swagger_auto_schema(
        tags=['Learning Content'],
        operation_id='learning-content-list',
        manual_parameters=[
            openapi.Parameter('section', openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('day', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('content_type', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
    )
    def get(self, request):
        try:
            is_management = self.section_is_management(request.query_params.get('section'))
            queryset = AdhdContent.objects.filter(
                status=ContentStatus.PUBLISHED,
                is_management=is_management,
                age_group=LearningContentService.user_age_group(request.user),
            )
            day = request.query_params.get('day')
            if day not in (None, ''):
                try:
                    day = int(day)
                except (TypeError, ValueError):
                    raise ValidationError({'day': 'A positive integer is required.'})
                if day < 1:
                    raise ValidationError({'day': 'A positive integer is required.'})
                queryset = queryset.filter(day=day)
            content_type = request.query_params.get('content_type')
            if content_type:
                queryset = queryset.filter(file_type=content_type)

            completed_attempts = ContentAttempt.objects.filter(
                user=request.user,
                content_id=OuterRef('pk'),
                status=AttemptStatus.COMPLETED,
            )
            queryset = queryset.annotate(
                question_count=Count('questions', filter=Q(questions__is_active=True), distinct=True),
                completed_at=Max(
                    'attempts__completed_at',
                    filter=Q(attempts__user=request.user, attempts__status=AttemptStatus.COMPLETED),
                ),
                user_completed=Exists(completed_attempts),
            ).order_by('day', 'order_number', 'id')

            total_days = queryset.aggregate(value=Max('day'))['value'] or 0
            unlocked_days = LearningContentService.unlocked_days(request.user)
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request, view=self)
            completed_ids = {content.id for content in page if content.user_completed}
            results = [self.serialize_content(content, request, unlocked_days, completed_ids) for content in page]
            return api_response(data={
                'section': 'management' if is_management else 'assessment',
                'current_day': max(unlocked_days) if is_management else None,
                'total_days': total_days,
                'has_active_subscription': user_has_active_subscription(request.user),
                'results': results,
                'pagination': {
                    'current_page': paginator.page.number,
                    'page_size': paginator.get_page_size(request),
                    'total_items': paginator.page.paginator.count,
                    'total_pages': paginator.page.paginator.num_pages,
                    'has_next': paginator.page.has_next(),
                    'has_previous': paginator.page.has_previous(),
                },
            })
        except ValidationError as exc:
            return api_response(message='Validation Error', status_code=status.HTTP_400_BAD_REQUEST, errors=exc.detail)


class LearningContentDetailApiView(LearningContentMixin, generics.GenericAPIView):
    serializer_class = StartAttemptSerializer

    def get(self, request, content_id):
        try:
            content = LearningContentService.accessible_content(content_id, request.user)
            questions = list(
                content.questions
                .filter(is_active=True)
                .prefetch_related('options')
                .order_by('display_order', 'id')
            )
            question_count = len(questions)
            completed = ContentAttempt.objects.filter(
                user=request.user, content=content, status=AttemptStatus.COMPLETED
            ).order_by('-completed_at').first()
            data = {
                'id': content.id,
                'title': content.title,
                'description': content.description,
                'content_type': content.file_type,
                'section': 'management' if content.is_management else 'assessment',
                'day': content.day,
                'display_order': content.order_number,
                'estimated_duration_minutes': content.estimated_duration_minutes,
                'cover_image_url': self.absolute_url(request, content.cover_image),
                'file_url': self.absolute_url(request, content.file),
                'article': (
                    {
                        'format': 'html',
                        'html': content.article_content,
                    }
                    if content.file_type == 'article' and content.article_content
                    else content.article_body if content.file_type == 'article' else None
                ),
                'activity_code': content.activity_name,
                'has_questions': question_count > 0,
                'question_count': question_count,
                'question_mode': content.question_mode if question_count else None,
                'questions': PublicContentQuestionSerializer(questions, many=True).data,
                'is_locked': False,
                'locked_reason': None,
                'is_completed': completed is not None,
                'completed_at': completed.completed_at if completed else None,
            }
            return api_response(data=data)
        except PermissionDenied as exc:
            return api_response(message=str(exc.detail), status_code=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return api_response(message='Validation Error', status_code=status.HTTP_404_NOT_FOUND, errors=exc.detail)


class StartContentAttemptApiView(LearningContentMixin, generics.GenericAPIView):
    serializer_class = StartAttemptSerializer

    def post(self, request, content_id):
        try:
            content = LearningContentService.accessible_content(content_id, request.user)
            attempt, created = LearningContentService.start_attempt(request.user, content)
            data = ContentAttemptSerializer(attempt).data
            data['created'] = created
            return api_response(data=data, status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        except PermissionDenied as exc:
            return api_response(message=str(exc.detail), status_code=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return api_response(message='Validation Error', status_code=status.HTTP_400_BAD_REQUEST, errors=exc.detail)


class AttemptQuestionsApiView(LearningContentMixin, generics.GenericAPIView):
    serializer_class = PublicContentQuestionSerializer

    def get(self, request, attempt_id):
        attempt = ContentAttempt.objects.filter(pk=attempt_id, user=request.user).select_related('content').first()
        if attempt is None:
            return api_response(message='Attempt not found.', status_code=status.HTTP_404_NOT_FOUND)
        questions = attempt.content.questions.filter(is_active=True).prefetch_related('options').order_by('display_order', 'id')
        return api_response(data={
            'content_id': attempt.content_id,
            'attempt_id': attempt.id,
            'question_mode': attempt.content.question_mode,
            'questions': self.serializer_class(questions, many=True).data,
        })


class SubmitContentAttemptApiView(LearningContentMixin, generics.GenericAPIView):
    serializer_class = SubmitAttemptSerializer

    def post(self, request, attempt_id):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return api_response(message='Validation Error', status_code=status.HTTP_400_BAD_REQUEST, errors=serializer.errors)
        try:
            attempt, submitted = LearningContentService.submit_attempt(
                request.user,
                attempt_id,
                serializer.validated_data['answers'],
            )
            data = ContentAttemptSerializer(attempt).data
            data['submitted'] = submitted
            data['answers'] = ContentAnswerResultSerializer(
                attempt.answers.prefetch_related('selected_options').order_by('question__display_order'),
                many=True,
            ).data
            return api_response(data=data)
        except PermissionDenied as exc:
            return api_response(message=str(exc.detail), status_code=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return api_response(message='Validation Error', status_code=status.HTTP_400_BAD_REQUEST, errors=exc.detail)


class ContentAttemptHistoryApiView(LearningContentMixin, generics.GenericAPIView):
    serializer_class = ContentAttemptSerializer

    def get(self, request, content_id):
        try:
            content = LearningContentService.accessible_content(content_id, request.user)
        except PermissionDenied as exc:
            return api_response(message=str(exc.detail), status_code=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            return api_response(message='Content not found.', status_code=status.HTTP_404_NOT_FOUND, errors=exc.detail)
        attempts = ContentAttempt.objects.filter(user=request.user, content=content).order_by('-attempt_number')
        return api_response(data={
            'content_id': content.id,
            'count': attempts.count(),
            'results': self.serializer_class(attempts, many=True).data,
        })
