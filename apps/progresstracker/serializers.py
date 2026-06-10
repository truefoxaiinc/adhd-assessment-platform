from rest_framework import serializers
from apps.progresstracker.models import UserAssessmentDetails,ProgressTracker
from django.utils.translation import gettext_lazy as _
from helpers.helper import get_object_or_none

class SaveDailyCompletedStatusSerializer(serializers.Serializer):
    day_number    = serializers.IntegerField(required=True)
    is_completed  = serializers.BooleanField(required=True)

    class Meta:
        model = ProgressTracker
        fields = ['day', 'is_completed']
    
    def validate(self, attrs):
        return super().validate(attrs)
    
    def save_user_assessment_details(self,data):
        user_assessment = data.get('user_assessment', None)
        user_assessment.last_completed    = data.get('day_number')
        user_assessment.user              = data.get('user')
        user_assessment.save()
        return user_assessment
    
    def create(self, validated_data):
        user = self.context['request'].user
        day_number = validated_data.get('day_number')
        is_completed = validated_data.get('is_completed')

        progress_tracker, created = ProgressTracker.objects.get_or_create(
            user=user,
            day_number=day_number,
            defaults={'is_completed': is_completed}
        )

        if not created:
            progress_tracker.is_completed = is_completed
            progress_tracker.save()

        user_assessment =get_object_or_none(UserAssessmentDetails, user=user)
        if user_assessment is None:
            user_assessment = UserAssessmentDetails()

        self.save_user_assessment_details({
            'user_assessment': user_assessment,
            'day_number': day_number,
            'user': user
        })
        return progress_tracker
    
    def update(self, instance, validated_data):
        instance.day_number = validated_data.get('day_number', instance.day_number)
        instance.is_completed = validated_data.get('is_completed', instance.is_completed)
        instance.save()
        user = self.context['request'].user

        user_assessment =get_object_or_none(UserAssessmentDetails, user=user)
        if user_assessment is None:
            user_assessment = UserAssessmentDetails()
        
        self.save_user_assessment_details({
            'user_assessment': get_object_or_none(UserAssessmentDetails, user=user),
            'day_number': validated_data.get('day_number'),
            'user': user
        })
        return instance
