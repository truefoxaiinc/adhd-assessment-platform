# serializers.py
from rest_framework import serializers
from .models import AdhdContent

class VideoUploadSerializer(serializers.Serializer):
    age_group       = serializers.ChoiceField(choices=["adult", "minor"],required=True)
    day             = serializers.IntegerField(min_value=1, max_value=7,required=True)
    video_number    = serializers.IntegerField(min_value=1, max_value=2,required=True)
    file            = serializers.FileField()




class AdhdContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdhdContent
        fields = '__all__'