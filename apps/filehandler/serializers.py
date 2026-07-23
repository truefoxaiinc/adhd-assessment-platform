# serializers.py
from rest_framework import serializers
from .models import AdhdContent, FileTypeCategory
from apps.progresstracker.services.track_services import ProgressTrackerActions

class VideoUploadSerializer(serializers.Serializer):
    age_group       = serializers.ChoiceField(choices=["adult", "minor"],required=True)
    day             = serializers.IntegerField(min_value=1, max_value=7,required=True)
    video_number    = serializers.IntegerField(min_value=1, max_value=2,required=True)
    file            = serializers.FileField()




class AdhdContentSerializer(serializers.ModelSerializer):
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = AdhdContent
        fields = "__all__"

    def get_is_locked(self, obj):
        unlocked_days = self.context.get("unlocked_days", [])

        if not obj.is_management:
            return False

        return obj.day not in unlocked_days

    def validate(self, attrs):
        file_type = attrs.get("file_type", getattr(self.instance, "file_type", None))
        activity_name = attrs.get("activity_name", getattr(self.instance, "activity_name", None))
        uploaded_file = attrs.get("file", getattr(self.instance, "file", None))

        if file_type == FileTypeCategory.ACTIVITY:
            if not activity_name:
                raise serializers.ValidationError({
                    "activity_name": "This field is required for activity content."
                })
            return attrs

        if not uploaded_file:
            raise serializers.ValidationError({
                "file": "This field is required for video/file content."
            })
        if activity_name:
            raise serializers.ValidationError({
                "activity_name": "Use this field only when file_type is activity."
            })

        return attrs


class UpdateLearningProgressSerializer(serializers.Serializer):
    file_id = serializers.PrimaryKeyRelatedField(
        queryset=AdhdContent.objects.all(),
        required=False,
        allow_null=False,
    )
    filetype = serializers.ChoiceField(choices=["video", "file", "document", "activity"], required=False)
    day_completed = serializers.IntegerField(required=False, min_value=1)
    order_number = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        unknown_fields = set(self.initial_data.keys()) - set(self.fields.keys())
        if unknown_fields:
            raise serializers.ValidationError({
                field: "Unknown field." for field in sorted(unknown_fields)
            })

        user = self.context["request"].user
        age_group = user.age_category or "adult"
        content = attrs.get("file_id")

        if content is None:
            required_fields = ["filetype", "day_completed", "order_number"]
            missing_fields = [
                field for field in required_fields
                if attrs.get(field) in (None, "")
            ]
            if missing_fields:
                raise serializers.ValidationError({
                    field: "This field is required when file_id is not supplied."
                    for field in missing_fields
                })

            content = (
                AdhdContent.objects
                .filter(
                    is_management=True,
                    age_group=age_group,
                    day=attrs["day_completed"],
                    file_type=attrs["filetype"],
                    order_number=attrs["order_number"],
                )
                .first()
            )
            if content is None:
                raise serializers.ValidationError({
                    "file_id": "Lesson/file does not exist for this user, day, type, and order."
                })
        else:
            if not content.is_management:
                raise serializers.ValidationError({
                    "file_id": "Only management lessons can update learning progress."
                })
            if content.age_group != age_group:
                raise serializers.ValidationError({
                    "file_id": "Lesson/file does not belong to this user's age group."
                })

            submitted_values = {
                "filetype": content.file_type,
                "day_completed": content.day,
                "order_number": content.order_number,
            }
            for field, expected_value in submitted_values.items():
                if attrs.get(field) is not None and attrs[field] != expected_value:
                    raise serializers.ValidationError({
                        field: "Does not match the supplied file_id."
                    })

        unlocked_days = ProgressTrackerActions.get_days_for_the_file(user) or [1]
        if content.day not in unlocked_days:
            raise serializers.ValidationError({
                "file_id": "Lesson/file is locked for this user."
            })

        attrs["content"] = content
        attrs["filetype"] = content.file_type
        attrs["day_completed"] = content.day
        attrs["order_number"] = content.order_number
        return attrs
