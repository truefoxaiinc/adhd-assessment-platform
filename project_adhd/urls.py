"""
URL configuration for alcan project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path,include,re_path
from django.views.generic.base import RedirectView
from django.views.static import serve
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls.static import static
from django.conf import settings
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.views.generic import RedirectView


schema_view             = get_schema_view(
        openapi.Info(
        title             = "ADHD API",
        default_version   = 'v1',
        description       = "",
        terms_of_service  = "",
        contact           = openapi.Contact(email="saleemsuhail48@gmail.com"),
        schemes=['http', 'https']
    ),
    public               = True,
    permission_classes   = [permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/api/docs'), name='redirect'),

    re_path(r'^media/(?P<path>.*)$', serve,{'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve,{'document_root': settings.STATIC_ROOT}),
    re_path(r'^assets/(?P<path>.*)$', serve,{'document_root': settings.STATIC_ROOT}),


    re_path(r'^api/', include([
        path('auth/',include('apps.authentication.urls')),
        path('users/',include('apps.users.urls')),
        path('assessment/',include('apps.assessment.urls')),
        path('websocket/',include('apps.websocket.urls')),
        path('filehandler/',include('apps.filehandler.urls')),
        path('articles/',include('apps.articles.urls')),

        re_path(r'^docs/', include([
            path('', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
        ])),
    ])),
]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

LOGIN_URL = '/auth/login'