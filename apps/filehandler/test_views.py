import pytest
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import Users
from apps.filehandler.models import AdhdContent
from apps.payments.models import (
    EntitlementStatus,
    StorePlatform,
    StorePurchase,
    SubscriptionEntitlement,
)
from apps.progresstracker.models import ProgressTracker, UserAssessmentDetails
from django.utils import timezone

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user():
    return Users.objects.create_user(
        username='file_test',
        email='file_test@test.com',
        password='Password123!',
        is_verified=True,
        dob='1990-01-01',
    )

@pytest.fixture
def child_user():
    return Users.objects.create_user(
        username='child_file_test',
        email='child_file_test@test.com',
        password='Password123!',
        is_verified=True,
        dob='2020-01-01',
    )

@pytest.fixture
def adult_day_one_video():
    return AdhdContent.objects.create(
        title='Adult Day 1 Video',
        file='adhd_content/adult-day-1-video.mp4',
        is_management=True,
        age_group='adult',
        day=1,
        file_type='video',
        order_number=1,
    )

@pytest.mark.django_db
class TestFileHandlerViews:
    UPDATE_PROGRESS_URL = '/api/filehandler/v1/filehandler/update-learning-progress/'
    LIST_FILES_URL = '/api/filehandler/v1/filehandler/list-all-files/'

    def test_update_learning_progress_saves_authenticated_user_progress(self, api_client, user, adult_day_one_video):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': adult_day_one_video.id},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        assert ProgressTracker.objects.filter(
            user=user,
            day_number=1,
            file_type='video',
            order_number='1',
        ).exists()

    def test_list_management_files_includes_daily_activity(self, api_client, user):
        AdhdContent.objects.create(
            title='Memory Flip',
            is_management=True,
            age_group='adult',
            day=1,
            file_type='activity',
            activity_name='memory_flip',
            order_number=5,
        )
        api_client.force_authenticate(user=user)

        response = api_client.get(self.LIST_FILES_URL, {'is_management': 'true'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] is True
        activity = response.data['data'][0]
        assert activity['file_type'] == 'activity'
        assert activity['activity_name'] == 'memory_flip'
        assert activity['file'] in ('', None)

    def test_update_learning_progress_saves_activity_progress(self, api_client, user):
        activity = AdhdContent.objects.create(
            title='Memory Flip',
            is_management=True,
            age_group='adult',
            day=1,
            file_type='activity',
            activity_name='memory_flip',
            order_number=5,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': activity.id},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert ProgressTracker.objects.filter(
            user=user,
            day_number=1,
            file_type='activity',
            order_number='5',
        ).exists()

    def test_update_learning_progress_rejects_invalid_file_id(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': 999999},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'file_id' in response.data['errors']

    def test_update_learning_progress_rejects_locked_lesson(self, api_client, user):
        locked_content = AdhdContent.objects.create(
            title='Adult Day 2 Video',
            file='adhd_content/adult-day-2-video.mp4',
            is_management=True,
            age_group='adult',
            day=2,
            file_type='video',
            order_number=1,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': locked_content.id},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['file_id'] == 'Lesson/file is locked for this user.'

    def test_day_two_stays_locked_without_active_subscription(self, api_client, user):
        day_two_content = AdhdContent.objects.create(
            title='Adult Day 2 Video',
            file='adhd_content/adult-day-2-video.mp4',
            is_management=True,
            age_group='adult',
            day=2,
            file_type='video',
            order_number=1,
        )
        UserAssessmentDetails.objects.create(
            user=user,
            last_completed=1,
            last_completed_at=timezone.now() - timezone.timedelta(days=1),
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': day_two_content.id},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['file_id'] == 'Lesson/file is locked for this user.'

    def test_day_two_unlocks_with_active_subscription_and_completed_day_one(self, api_client, user):
        day_two_content = AdhdContent.objects.create(
            title='Adult Day 2 Video',
            file='adhd_content/adult-day-2-video.mp4',
            is_management=True,
            age_group='adult',
            day=2,
            file_type='video',
            order_number=1,
        )
        UserAssessmentDetails.objects.create(
            user=user,
            last_completed=1,
            last_completed_at=timezone.now() - timezone.timedelta(days=1),
        )
        purchase = StorePurchase.objects.create(
            user=user,
            platform=StorePlatform.ANDROID,
            product_id='attentionminder.monthly',
            store_purchase_id='active-day-two-token',
            status=EntitlementStatus.ACTIVE,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        SubscriptionEntitlement.objects.create(
            user=user,
            platform=StorePlatform.ANDROID,
            product_id=purchase.product_id,
            status=EntitlementStatus.ACTIVE,
            expires_at=purchase.expires_at,
            source_purchase=purchase,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': day_two_content.id},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert ProgressTracker.objects.filter(
            user=user,
            day_number=2,
            file_type='video',
        ).exists()

    def test_day_two_stays_locked_after_subscription_expires(self, api_client, user):
        day_two_content = AdhdContent.objects.create(
            title='Adult Day 2 Video',
            file='adhd_content/adult-day-2-video.mp4',
            is_management=True,
            age_group='adult',
            day=2,
            file_type='video',
            order_number=1,
        )
        UserAssessmentDetails.objects.create(
            user=user,
            last_completed=1,
            last_completed_at=timezone.now() - timezone.timedelta(days=1),
        )
        purchase = StorePurchase.objects.create(
            user=user,
            platform=StorePlatform.ANDROID,
            product_id='attentionminder.monthly',
            store_purchase_id='expired-day-two-token',
            status=EntitlementStatus.EXPIRED,
            expires_at=timezone.now() - timezone.timedelta(seconds=1),
        )
        SubscriptionEntitlement.objects.create(
            user=user,
            platform=StorePlatform.ANDROID,
            product_id=purchase.product_id,
            status=EntitlementStatus.EXPIRED,
            expires_at=purchase.expires_at,
            source_purchase=purchase,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': day_two_content.id},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['file_id'] == 'Lesson/file is locked for this user.'

    def test_update_learning_progress_rejects_wrong_age_group_lesson(self, api_client, child_user, adult_day_one_video):
        api_client.force_authenticate(user=child_user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': adult_day_one_video.id},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['file_id'] == "Lesson/file does not belong to this user's age group."

    def test_update_learning_progress_rejects_user_id_payload(self, api_client, user, adult_day_one_video):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {
                'file_id': adult_day_one_video.id,
                'user_id': user.id,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['user_id'] == 'Unknown field.'

    def test_update_learning_progress_legacy_fields_must_match_lesson(self, api_client, user, adult_day_one_video):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {
                'file_id': adult_day_one_video.id,
                'filetype': 'file',
                'day_completed': 1,
                'order_number': 1,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['errors']['filetype'] == 'Does not match the supplied file_id.'

    def test_update_learning_progress_legacy_payload_verifies_lesson_exists(self, api_client, user, adult_day_one_video):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {
                'filetype': 'video',
                'day_completed': 1,
                'order_number': 1,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert ProgressTracker.objects.filter(user=user, day_number=1, file_type='video').exists()

    def test_update_learning_progress_legacy_payload_rejects_missing_lesson(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {
                'filetype': 'video',
                'day_completed': 1,
                'order_number': 1,
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'file_id' in response.data['errors']

    def test_update_learning_progress_is_scoped_to_authenticated_user(self, api_client, user, adult_day_one_video):
        other_user = Users.objects.create_user(
            username='other_progress_user',
            email='other_progress_user@test.com',
            password='Password123!',
            is_verified=True,
            dob='1990-01-01',
        )
        ProgressTracker.objects.create(
            user=other_user,
            day_number=1,
            file_type='video',
            order_number='1',
            is_day_completed=True,
        )
        api_client.force_authenticate(user=user)

        response = api_client.post(
            self.UPDATE_PROGRESS_URL,
            {'file_id': adult_day_one_video.id},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert ProgressTracker.objects.filter(user=other_user).count() == 1
        assert ProgressTracker.objects.filter(user=user, day_number=1, file_type='video').count() == 1
