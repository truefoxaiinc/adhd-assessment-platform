import pytest
from rest_framework import status
from django.urls import reverse
from apps.users.models import Users

@pytest.mark.django_db
class TestAuthenticationViews:
    def setup_method(self):
        self.user = Users.objects.create_user(
            username='auth_test',
            email='auth_test@test.com',
            password='Password123!',
            is_verified=True
        )

    def test_login_success(self, client):
        url = '/api/auth/v1/login/'
        data = {
            'email': 'auth_test@test.com',
            'password': 'Password123!'
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] is True
        assert 'access' in response.data['data']

    def test_login_invalid_password(self, client):
        url = '/api/auth/v1/login/'
        data = {
            'email': 'auth_test@test.com',
            'password': 'wrongpassword'
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_invalid_email(self, client):
        url = '/api/auth/v1/login/'
        data = {
            'email': 'doesnotexist@test.com',
            'password': 'Password123!'
        }
        response = client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_unverified_user(self, client):
        Users.objects.create_user(
            username='unverified',
            email='unverified@test.com',
            password='Password123!',
            is_verified=False
        )
        url = '/api/auth/v1/login/'
        data = {
            'email': 'unverified@test.com',
            'password': 'Password123!'
        }
        response = client.post(url, data, format='json')
        # Expect either 400 or 401 depending on the exact logic
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED]

    def test_login_missing_fields(self, client):
        url = '/api/auth/v1/login/'
        response = client.post(url, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_success(self, client):
        login_url = '/api/auth/v1/login/'
        login_data = {
            'email': 'auth_test@test.com',
            'password': 'Password123!'
        }
        login_response = client.post(login_url, login_data, format='json')
        assert login_response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        refresh_token = login_response.data['data']['tokens']['refresh']

        logout_url = '/api/auth/v1/logout/'
        logout_data = {
            'refresh': refresh_token
        }
        logout_response = client.post(logout_url, logout_data, format='json')
        assert logout_response.status_code == status.HTTP_200_OK
        assert logout_response.data['status'] is True

    def test_logout_invalid_refresh_token(self, client):
        logout_url = '/api/auth/v1/logout/'
        logout_data = {
            'refresh': 'invalid-token'
        }
        response = client.post(logout_url, logout_data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
