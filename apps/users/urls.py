from django.urls import path,re_path,include
from . import views

app_name = 'users'
   
urlpatterns = [
    re_path(r'^v1/', include([
        re_path(r'^users/', include([
            path('registration', views.UserRegistrationApiView.as_view()),
            path('update-profile', views.UserUpdateProfileApiView.as_view()),
            path('get-user-profile', views.GetUserProfileDetailApiView.as_view()),
            path('password-reset/request', views.PasswordResetRequestApiView.as_view()),
            path('password-reset/otp-verify', views.PasswordResetOTPVerifyApiView.as_view()),
            path('password-reset/change', views.PasswordChangeApiView.as_view()),
            path('social-login', views.SocialLoginView.as_view()),
        ])),

    ]))
]