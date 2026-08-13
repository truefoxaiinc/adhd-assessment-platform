from django.urls import path

from apps.filehandler import learning_views


app_name = 'learning-content'

urlpatterns = [
    path('v1/contents', learning_views.LearningContentListApiView.as_view(), name='content-list'),
    path('v1/contents/<int:content_id>', learning_views.LearningContentDetailApiView.as_view(), name='content-detail'),
    path('v1/contents/<int:content_id>/submit', learning_views.SubmitContentAnswersApiView.as_view(), name='content-submit'),
    path('v1/contents/<int:content_id>/attempt-history', learning_views.ContentAttemptHistoryApiView.as_view(), name='attempt-history'),
    path('v1/attempts/<uuid:attempt_id>/questions', learning_views.AttemptQuestionsApiView.as_view(), name='attempt-questions'),
    path('v1/attempts/<uuid:attempt_id>/submit', learning_views.SubmitContentAttemptApiView.as_view(), name='attempt-submit'),
]
