from rest_framework import serializers
from apps.users.models import Users
from rest_framework_simplejwt.tokens import RefreshToken


"""Login"""
class GetLoginResponseSchema(serializers.ModelSerializer):
    username    = serializers.CharField(allow_null=True)
    email       = serializers.EmailField(allow_null=True)
    tokens      = serializers.SerializerMethodField()

    class Meta:
        model = Users
        fields = ['id','username','email','is_first','is_last','tokens']

    def get_tokens(self,instance):
        refresh = RefreshToken.for_user(instance)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        data=  {
            'access': access_token,
            'refresh': refresh_token,
            'token_type': 'Bearer'
        }
        return data


    def to_representation(self, instance):
        datas = super().to_representation(instance)
        for key in datas.keys():
            try:
                if datas[key] is None:
                    datas[key] = ""
            except KeyError:
                pass
        return datas
