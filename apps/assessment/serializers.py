from rest_framework import serializers
from .models import SelfAssessmentResponse,SelfAssessmentResult,SelfAssessmentQuestions
from helpers.helper import get_token_user_or_none,get_object_or_none
from services.assessment_result.assessment_result_services import ResultService
from rest_framework.exceptions import ValidationError


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

    class Meta:
        model = SelfAssessmentResult
        fields = ['assesment']


    def validate(self, attrs):
        return super().validate(attrs)


    def create(self, validated_data):
        request = self.context.get('request',None)

        assessment_results = validated_data.get('assesment',[])
        user_instance = get_token_user_or_none(request)


        instance = SelfAssessmentResult.objects.filter(user=user_instance).order_by('-id').first()
        if not instance:
            instance = SelfAssessmentResult()
            instance.user = user_instance
            instance.save()

        for results in assessment_results:
            sub_serializer = SelfAssessmentSubSerializer(data=results,context={'request':request,'result_instance':instance})
            sub_serializer.is_valid(raise_exception=True)
            sub_serializer.save()

        is_adult = user_instance.adult

        instance = ResultService(instance,is_adult).calculate_selfassessment()

        return instance
