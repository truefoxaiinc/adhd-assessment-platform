from django.urls import path,re_path,include
from . import views

app_name = 'assessment'
   
urlpatterns = [
    re_path(r'^v1/', include([
        re_path(r'^self-assessment/', include([
            path('get-questions', views.GetSelfAssessmentQuestionsListApiView.as_view()),
            path('save-response', views.SelfAssessmentResponseApiView.as_view()),
            path('fetch-result', views.ResultFetchApiView.as_view()),
            path('result-history', views.ResultHistoryApiView.as_view()),
            path('progress', views.SelfAssessmentProgressApiView.as_view()),

        ])),

    ]))
]
