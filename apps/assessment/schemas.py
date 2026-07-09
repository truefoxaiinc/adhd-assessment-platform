from rest_framework import serializers
from apps.assessment.models import SelfAssessmentQuestions,SelfAssessmentResult


class SelfAssessmentQuestionsListSchema(serializers.ModelSerializer):
    class Meta:
        model = SelfAssessmentQuestions
        fields = ['id','question_text','category']


    def to_representation(self, instance):
        datas = super().to_representation(instance)
        for key in datas.keys():
            try:
                if datas[key] is None:
                    datas[key] = ""
            except KeyError:
                pass
        return datas
    



class SelfAssessmentResultSchema(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username',allow_null=True)
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = SelfAssessmentResult
        fields = ['id','user','result','raw_total','tenscore','read_focus_total','visual_tracking_total','audio_listening_total','program_duration','is_completed','created_at','completed_at']

    def get_is_completed(self, instance):
        return instance.completed_at is not None


    def to_representation(self, instance):
        datas = super().to_representation(instance)
        for key in datas.keys():
            try:
                if datas[key] is None:
                    datas[key] = ""
            except KeyError:
                pass
        return datas
