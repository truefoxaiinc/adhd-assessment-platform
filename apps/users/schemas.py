from rest_framework import serializers
from apps.assessment.models import SelfAssessmentResult
from apps.payments.models import SubscriptionEntitlement
from apps.progresstracker.models import FaceAttentionSession
from apps.users.models import Users


"""User Profile Schema"""
class GetUserProfileDetailSchema(serializers.ModelSerializer):
    profile_image_url = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()
    has_active_subscription = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()
    subscription_expires_at = serializers.SerializerMethodField()
    questionnaire_done = serializers.SerializerMethodField()
    ai_assessment_done = serializers.SerializerMethodField()

    class Meta:
        model = Users
        fields = [
            'id',
            'email',
            'username',
            'dob',
            'gender',
            'country',
            'profile_image',
            'profile_image_url',
            'is_first',
            'is_last',
            'is_completed',
            'has_active_subscription',
            'subscription_status',
            'subscription_expires_at',
            'questionnaire_done',
            'ai_assessment_done',
        ]

    def _get_subscription_entitlement(self, instance):
        cache_attribute = '_profile_subscription_entitlement'
        if not hasattr(instance, cache_attribute):
            entitlement = SubscriptionEntitlement.objects.filter(user_id=instance.pk).first()
            setattr(instance, cache_attribute, entitlement)
        return getattr(instance, cache_attribute)

    def get_profile_image_url(self, instance):
        request = self.context.get('request')
        if not instance.profile_image:
            return None
        image_url = instance.profile_image.url
        if request:
            return request.build_absolute_uri(image_url)
        return image_url

    def get_is_completed(self, instance):
        required_fields = [
            instance.email,
            instance.username,
            instance.dob,
            instance.gender,
            instance.country,
        ]
        return all(bool(value) for value in required_fields)

    def get_has_active_subscription(self, instance):
        entitlement = self._get_subscription_entitlement(instance)
        return bool(entitlement and entitlement.is_active)

    def get_subscription_status(self, instance):
        entitlement = self._get_subscription_entitlement(instance)
        return entitlement.status if entitlement else 'inactive'

    def get_subscription_expires_at(self, instance):
        entitlement = self._get_subscription_entitlement(instance)
        if not entitlement or not entitlement.expires_at:
            return None
        return serializers.DateTimeField().to_representation(entitlement.expires_at)

    def get_questionnaire_done(self, instance):
        return SelfAssessmentResult.objects.filter(
            user_id=instance.pk,
            completed_at__isnull=False,
        ).exists()

    def get_ai_assessment_done(self, instance):
        return FaceAttentionSession.objects.filter(
            user_id=instance.pk,
            is_assessment=True,
        ).exists()

    def to_representation(self, instance):
        datas = super().to_representation(instance)
        for key in datas.keys():
            try:
                if datas[key] is None:
                    datas[key] = ""
            except KeyError:
                pass
        if not instance.profile_image:
            datas['profile_image'] = None
            datas['profile_image_url'] = None
        return datas
