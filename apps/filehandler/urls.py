from django.urls import path, re_path, include
from .views import (
    FetchS3Files,
    SaveFeedbackforAIAssessment,
    FileUploadView,
    UpdateLearningProgress,
    ListAllFiles,
)

app_name = 'filehandler'

urlpatterns = [
    re_path(r'^v1/', include([
        re_path(r'^filehandler/', include([
            path('get-files', FetchS3Files.as_view()),
            path('list-files', ListAllFiles.as_view(), name='list-files'),
            path('save-feedback', SaveFeedbackforAIAssessment.as_view()),
            path('upload-file/', FileUploadView.as_view(), name='upload-file'),
            path('update-learning-progress/', UpdateLearningProgress.as_view(), name='update-learning-progress'),
        ])),
    ]))
]