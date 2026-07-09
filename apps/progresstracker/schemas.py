from rest_framework import serializers

from apps.progresstracker.models import FaceAttentionSession


class FaceAttentionSessionSchema(serializers.ModelSerializer):
    attention_score = serializers.SerializerMethodField()

    class Meta:
        model = FaceAttentionSession
        fields = [
            'id',
            'session_id',
            'attention_score',
            'concentration_score',
            'average_concentration_score',
            'attention_engagement_rate',
            'average_confidence',
            'session_duration_seconds',
            'total_processed_frames',
            'sampled_frames',
            'bad_frame_count',
            'blurry_frame_count',
            'low_light_frame_count',
            'eyes_closed_count',
            'gaze_warning_count',
            'face_detected',
            'video_attentive',
            'eyes_closed',
            'yawning',
            'gaze_state',
            'head_pose_ok',
            'low_light',
            'gaze_ratio_avg',
            'inattention_duration',
            'brightness_score',
            'pitch',
            'yaw',
            'roll',
            'blink_ratio',
            'yawn_distance',
            'created_at',
        ]

    def get_attention_score(self, instance):
        raw_score = (
            instance.average_concentration_score
            if instance.average_concentration_score is not None
            else instance.concentration_score
        )
        return round(max(0.0, min(float(raw_score or 0.0), 8.0)) / 8.0 * 100, 2)
