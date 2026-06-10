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

    class Meta:
        model = SelfAssessmentResult
        fields = ['id','user','result','raw_total','tenscore','read_focus_total','visual_tracking_total','audio_listening_total','program_duration']


    def to_representation(self, instance):
        datas = super().to_representation(instance)
        for key in datas.keys():
            try:
                if datas[key] is None:
                    datas[key] = ""
            except KeyError:
                pass
        return datas