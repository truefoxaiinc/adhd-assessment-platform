from rest_framework import serializers
from apps.users.models import Users


"""User Profile Schema"""
class GetUserProfileDetailSchema(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Users
        fields = ['id', 'email', 'username', 'dob', 'gender', 'country', 'height', 'weight', 'profile_image', 'profile_image_url']

    def get_profile_image_url(self, instance):
        request = self.context.get('request')
        if not instance.profile_image:
            return ""
        image_url = instance.profile_image.url
        if request:
            return request.build_absolute_uri(image_url)
        return image_url

    def to_representation(self, instance):
        datas = super().to_representation(instance)
        for key in datas.keys():
            try:
                if datas[key] is None:
                    datas[key] = ""
            except KeyError:
                pass
        return datas
