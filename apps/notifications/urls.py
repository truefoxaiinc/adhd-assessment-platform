from django.urls import include, path, re_path

from apps.notifications import views


app_name = 'notifications'

urlpatterns = [
    re_path(r'^v1/', include([
        re_path(r'^devices/', include([
            path('register/', views.RegisterPushDeviceApiView.as_view(), name='register-device'),
            path('unregister/', views.UnregisterPushDeviceApiView.as_view(), name='unregister-device'),
        ])),
    ])),
]
