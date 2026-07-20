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
        fields = ['id','user','result','raw_total','tenscore','read_focus_total','visual_tracking_total','audio_listening_total','is_completed','created_at','completed_at']

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
            'content_type',
            'is_assessment',
            'calculation_version',
            'score',
            'final_score',
            'concentration_score',
            'average_concentration_score',
            'attention_engagement_rate',
            'reading_engagement_rate',
            'average_confidence',
            'total_processed_frames',
            'sampled_frames',
            'reading_focused_frames',
            'watching_video_frames',
            'idle_distracted_frames',
            'session_duration_seconds',
            'inattention_duration',
            'maximum_inattention_duration',
            'gaze_ratio_avg',
            'gaze_quality_avg',
            'reading_gaze_frequency_avg_hz',
            'reading_gaze_amplitude_avg',
            'drowsy_state',
            'brightness_score',
            'pitch',
            'yaw',
            'roll',
            'blink_ratio',
            'yawn_distance',
            'bad_frame_count',
            'blurry_frame_count',
            'low_light_frame_count',
            'eyes_closed_count',
            'gaze_warning_count',
            'created_at',
        ]

    def get_score(self, instance):
        concentration = instance.average_concentration_score
        return round((concentration / 8.0) * 100, 2)
