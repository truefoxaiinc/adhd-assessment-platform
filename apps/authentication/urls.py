from django.urls import path,re_path,include
from . import views
   
urlpatterns = [
    re_path(r'^v1/', include([
        path('login/', views.LoginApiView.as_view()),
        path('logout/', views.LogoutApiView.as_view()),
    ]))
]