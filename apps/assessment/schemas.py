from rest_framework import serializers
from apps.assessment.models import SelfAssessmentQuestions,SelfAssessmentResult
from apps.progresstracker.models import FaceAttentionSession


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


class AIAssessmentScoreSchema(serializers.ModelSerializer):
    score = serializers.SerializerMethodField()
    file_id = serializers.IntegerField(allow_null=True)

    class Meta:
        model = FaceAttentionSession
        fields = [
            'id',
            'session_id',
            'file_id',
            'is_assessment',
            'score',
            'concentration_score',
            'average_concentration_score',
            'attention_engagement_rate',
            'average_confidence',
            'total_processed_frames',
            'session_duration_seconds',
            'created_at',
        ]

    def get_score(self, instance):
        concentration = instance.average_concentration_score
        return round((concentration / 8.0) * 100, 2)
