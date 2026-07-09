from rest_framework import serializers
from apps.assessment.models import SelfAssessmentResponse,SelfAssessmentResult,SelfAssessmentQuestions
from apps.assessment.services.assessment_service import AssessmentService
from helpers.helper import get_token_user_or_none,get_object_or_none
from rest_framework.exceptions import ValidationError
from django.db import transaction


"""Self Assessment Serializers"""


"""Self Assessment Serializers"""

class SelfAssessmentSubSerializer(serializers.ModelSerializer):
    question        = serializers.IntegerField(allow_null=True, required=False)
    response        = serializers.ChoiceField(choices=SelfAssessmentResponse.RESPONSE_CHOICES.choices,allow_null=True, required=False)
    text_response   = serializers.CharField(allow_null=True, required=False)

    class Meta:
        model = SelfAssessmentResponse
        fields = ['id','question','response','text_response']

    def validate(self,attrs):
        return super().validate(attrs)
    
    def create(self,validated_data):
        result_instance = self.context.get('result_instance',None)

        question_instance = get_object_or_none(SelfAssessmentQuestions,pk=validated_data.get('question'))
        if question_instance is None:
            raise ValidationError({'question': 'Invalid question id.'})

        instance = SelfAssessmentResponse.objects.filter(result_entry=result_instance,question=question_instance).first()

        if instance:
            # Silently ignore to prevent 400 error when frontend sends already answered questions
            return instance

        instance                = SelfAssessmentResponse()
        instance.result_entry   = result_instance
        instance.question       = question_instance
        instance.response       = validated_data.get('response')
        instance.text_response  = validated_data.get('text_response',None)
        instance.save()

        return instance


class SelfAssessmentResponseSerializer(serializers.ModelSerializer):
    assesment   = serializers.ListField(child=SelfAssessmentSubSerializer(),allow_empty=False)
    retake      = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = SelfAssessmentResult
        fields = ['assesment', 'retake']


    def validate(self, attrs):
        return super().validate(attrs)


    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request',None)

        assessment_results = validated_data.get('assesment',[])
        retake = validated_data.get('retake', False)
        user_instance = get_token_user_or_none(request)
        is_adult = bool(user_instance.adult)

        instance = AssessmentService.get_or_create_result_for_user(
            user_instance,
            is_adult,
            retake=retake,
        )

        for results in assessment_results:
            sub_serializer = SelfAssessmentSubSerializer(data=results,context={'request':request,'result_instance':instance})
            sub_serializer.is_valid(raise_exception=True)
            sub_serializer.save()

        if AssessmentService.is_result_complete(instance, is_adult):
            instance = AssessmentService.calculate_result(instance, is_adult)

        return instance
