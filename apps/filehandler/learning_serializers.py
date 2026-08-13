from rest_framework import serializers

from apps.filehandler.models import (
    ContentAnswer,
    ContentAttempt,
    ContentQuestion,
    QuestionOption,
)


class PublicQuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'option_text', 'display_order']


class PublicContentQuestionSerializer(serializers.ModelSerializer):
    options = PublicQuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ContentQuestion
        fields = [
            'id',
            'question_text',
            'question_type',
            'display_order',
            'maximum_score',
            'is_required',
            'options',
        ]


class ContentDetailQuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'option_text', 'display_order', 'is_correct']


class ContentDetailQuestionSerializer(serializers.ModelSerializer):
    options = ContentDetailQuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ContentQuestion
        fields = [
            'id',
            'question_text',
            'question_type',
            'display_order',
            'maximum_score',
            'is_required',
            'explanation',
            'options',
        ]


class SubmittedAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    selected_option_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_selected_option_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Duplicate option IDs are not allowed.')
        return value


class EmptySerializer(serializers.Serializer):
    pass


class AnswersSerializer(serializers.Serializer):
    answers = SubmittedAnswerSerializer(many=True, required=False, default=list)

    def validate_answers(self, value):
        question_ids = [answer['question_id'] for answer in value]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError('Each question may be answered only once.')
        return value


class DirectContentSubmitSerializer(AnswersSerializer):
    answers = SubmittedAnswerSerializer(many=True, required=True, allow_empty=False)


class SubmitAttemptSerializer(AnswersSerializer):
    pass


class ContentAnswerResultSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(read_only=True)
    selected_option_ids = serializers.SerializerMethodField()

    class Meta:
        model = ContentAnswer
        fields = ['question_id', 'selected_option_ids', 'is_correct', 'awarded_score']

    def get_selected_option_ids(self, instance):
        return list(instance.selected_options.values_list('id', flat=True))


class ContentAttemptSerializer(serializers.ModelSerializer):
    content_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ContentAttempt
        fields = [
            'id',
            'content_id',
            'attempt_number',
            'status',
            'score',
            'maximum_score',
            'percentage',
            'passed',
            'started_at',
            'completed_at',
        ]
