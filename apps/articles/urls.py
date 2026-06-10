from django.urls import path,re_path,include
from . import views

app_name = 'articles'
   
urlpatterns = [
    re_path(r'^v1/', include([
        path('list', views.ArticleListApiView.as_view()),
    ]))
]
