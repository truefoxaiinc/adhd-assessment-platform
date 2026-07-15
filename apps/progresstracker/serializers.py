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
    is_last = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = UserGoal
        fields = [
            'id',
            'goal',
            'rating',
            'is_last',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate_goal(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Goal is required.')
        return value

    def validate_rating(self, value):
        if value < 0 or value > 5:
            raise serializers.ValidationError('Use a rating between 0 and 5.')
        return value

    def create(self, validated_data):
        validated_data.pop('is_last', None)
        user = self.context['request'].user
        return UserGoal.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        is_last = validated_data.pop('is_last', None)
        instance.goal = validated_data.get('goal', instance.goal)
        instance.rating = validated_data.get('rating', instance.rating)
        instance.save()

        if is_last is not None:
            user = self.context['request'].user
            user.is_last = is_last
            if user.is_last:
                user.is_first = False
            user.save(update_fields=['is_first', 'is_last'])

        return instance


class UserGoalBulkCreateSerializer(serializers.Serializer):
    goals = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
        required=True,
    )
    is_last = serializers.BooleanField(required=False, default=False)

    def validate_goals(self, value):
        normalized_goals = []
        for index, goal_item in enumerate(value):
            serializer = UserGoalSerializer(data=goal_item)
            if not serializer.is_valid():
                raise serializers.ValidationError({
                    index: serializer.errors
                })
            normalized_goals.append(serializer.validated_data)
        return normalized_goals

    def create(self, validated_data):
        user = self.context['request'].user
        goals = [
            UserGoal.objects.create(user=user, **goal)
            for goal in validated_data['goals']
        ]

        update_fields = []
        if user.is_first:
            user.is_first = False
            update_fields.append('is_first')
        if validated_data.get('is_last') is True and not user.is_last:
            user.is_last = True
            update_fields.append('is_last')
        if update_fields:
            user.save(update_fields=update_fields)

        return goals


class UserGoalBulkUpdateSerializer(serializers.Serializer):
    goals = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
        required=True,
    )
    is_last = serializers.BooleanField(required=False)

    def validate_goals(self, value):
        user = self.context['request'].user
        normalized_goals = []

        for index, goal_item in enumerate(value):
            goal_id = goal_item.get('id')
            if not goal_id:
                raise serializers.ValidationError({
                    index: {'id': 'This field is required.'}
                })

            instance = UserGoal.objects.filter(id=goal_id, user=user).first()
            if instance is None:
                raise serializers.ValidationError({
                    index: {'id': 'Invalid goal id.'}
                })

            serializer = UserGoalSerializer(instance, data=goal_item, partial=True)
            if not serializer.is_valid():
                raise serializers.ValidationError({
                    index: serializer.errors
                })

            normalized_goals.append({
                'instance': instance,
                'data': serializer.validated_data,
            })

        return normalized_goals

    def save(self):
        user = self.context['request'].user
        updated_goals = []

        for goal_item in self.validated_data['goals']:
            instance = goal_item['instance']
            data = goal_item['data']
            instance.goal = data.get('goal', instance.goal)
            instance.rating = data.get('rating', instance.rating)
            instance.save()
            updated_goals.append(instance)

        if 'is_last' in self.validated_data:
            user.is_last = self.validated_data['is_last']
            if user.is_last:
                user.is_first = False
            user.save(update_fields=['is_first', 'is_last'])

        return updated_goals
