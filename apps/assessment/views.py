from rest_framework import generics,status
from drf_yasg.utils import swagger_auto_schema
from helpers.helper import get_token_user_or_none
from helpers.response import ResponseInfo
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from helpers.custom_messages import _success
import  os,sys
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)
from apps.assessment.models import SelfAssessmentQuestions, SelfAssessmentResponse, SelfAssessmentResult
from helpers.custom_messages import _success,_record_not_found
from services.assessment_result.assessment_result_services import ResultService
from .schemas import (
    SelfAssessmentQuestionsListSchema,SelfAssessmentResultSchema
)
from .serializers import (
    SelfAssessmentResponseSerializer
)
from .cache import cache_get, cache_set, get_progress_cache_key, get_questions_cache_key, get_result_cache_key


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
            is_for_adults   = user_instance.adult

            cache_key = get_questions_cache_key(request, is_for_adults)
            cached_data = cache_get(cache_key)
            if cached_data:
                return Response(cached_data, status=status.HTTP_200_OK)

            queryset = (
                SelfAssessmentQuestions.objects
                .filter(Q(is_for_adults=is_for_adults) & Q(is_active=True))
                .only('id', 'question_text', 'category', 'is_for_adults', 'is_active')
                .order_by('-id')
            )
            data = self.serializer_class(queryset, many=True, context={'request': request}).data

            final_data = {"questions": data}

            self.response_format['status_code'] = status.HTTP_200_OK
            self.response_format["status"] = True
            self.response_format["message"] = _success
            self.response_format["data"] = final_data
            
            cache_set(cache_key, self.response_format)
            return Response(self.response_format, status=status.HTTP_200_OK)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

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

            # --- Log Answered and Unanswered Questions ---
            try:
                user_instance = get_token_user_or_none(request)
                all_questions = SelfAssessmentQuestions.objects.filter(
                    is_for_adults=user_instance.adult, 
                    is_active=True
                ).values_list('id', 'question_text')

                answered_question_ids = SelfAssessmentResponse.objects.filter(
                    result_entry=instance
                ).values_list('question_id', flat=True)

                answered = [q for q in all_questions if q[0] in answered_question_ids]
                unanswered = [q for q in all_questions if q[0] not in answered_question_ids]

                log_lines = ["\n=== Answered Questions ==="]
                for q in answered:
                    log_lines.append(f"ID: {q[0]} - {q[1]}")

                log_lines.append("\n=== Unanswered Questions ===")
                for q in unanswered:
                    log_lines.append(f"ID: {q[0]} - {q[1]}")
                log_lines.append("==========================\n")
                
                logger.info("\n".join(log_lines))
            except Exception as e:
                logger.error(f"Error logging questions status: {str(e)}")
            # -----------------------------------------------

            from .cache import bump_user_result_cache
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
            print(f"error is {e}")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


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
            is_for_adults = user_instance.adult

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
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




























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
            ResultService(instance,is_adult).calculate_selfassessment()

            self.response_format['status_code'] = status.HTTP_201_CREATED
            self.response_format["message"] = _success
            self.response_format["status"] = True
            return Response(self.response_format, status=status.HTTP_201_CREATED)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
