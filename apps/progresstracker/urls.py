from django.urls import path,re_path,include
from . import views

app_name = 'users'
   
urlpatterns = [
    re_path(r'^v1/', include([
        re_path(r'^progress-track/', include([
            path('save-daily-status', views.SaveDailyCompletedStatus.as_view()),
        ])),

    ]))
]