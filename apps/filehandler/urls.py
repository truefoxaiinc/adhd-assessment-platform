from django.urls import path, re_path, include
from .views import (
    SaveFeedbackforAIAssessment,
    UpdateLearningProgress,
    ListAllFiles,
)

app_name = 'filehandler'

urlpatterns = [
    re_path(r'^v1/', include([
        re_path(r'^filehandler/', include([
            path('list-files', ListAllFiles.as_view(), name='list-files'),
            path('save-feedback', SaveFeedbackforAIAssessment.as_view()),
            path('update-learning-progress/', UpdateLearningProgress.as_view(), name='update-learning-progress'),
        ])),
    ]))
]
