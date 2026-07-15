from rest_framework import serializers
from apps.progresstracker.models import UserAssessmentDetails,ProgressTracker,UserGoal
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


class UserGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserGoal
        fields = [
            'id',
            'goal',
            'rating',
            'is_first',
            'is_last',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'is_first', 'created_at', 'updated_at']

    def validate_rating(self, value):
        if value < 0 or value > 5:
            raise serializers.ValidationError('Use a rating between 0 and 5.')
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        instance = UserGoal.objects.create(user=user, **validated_data)
        if instance.is_last:
            UserGoal.objects.filter(user=user).exclude(pk=instance.pk).update(is_last=False)
        return instance

    def update(self, instance, validated_data):
        instance.goal = validated_data.get('goal', instance.goal)
        instance.rating = validated_data.get('rating', instance.rating)
        instance.is_last = validated_data.get('is_last', instance.is_last)
        instance.save()

        if instance.is_last:
            UserGoal.objects.filter(user=instance.user).exclude(pk=instance.pk).update(is_last=False)

        return instance


class UserGoalListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserGoal
        fields = [
            'id',
            'goal',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class UserGoalBulkCreateSerializer(serializers.Serializer):
    goals = serializers.ListField(
        child=serializers.CharField(allow_blank=False, trim_whitespace=True),
        allow_empty=False,
        required=True,
    )
    rating = serializers.IntegerField(required=False, default=0, min_value=0, max_value=5)

    def create(self, validated_data):
        user = self.context['request'].user
        rating = validated_data.get('rating', 0)
        return [
            UserGoal.objects.create(user=user, goal=goal, rating=rating)
            for goal in validated_data['goals']
        ]
