import hashlib
import json
import os
import sys
from copy import deepcopy

from django.core.cache import cache
from django.db.models import Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from helpers.custom_messages import _success
from helpers.pagination import CustomRestPagination
from helpers.response import ResponseInfo

from .models import Article
from .serializers import ArticleSerializer


ARTICLE_LIST_CACHE_TIMEOUT = 60 * 15
ARTICLE_CACHE_VERSION_KEY = 'articles:list:version'


def get_cache_value(key, default=None):
    try:
        return cache.get(key, default)
    except Exception:
        return default


def set_cache_value(key, value, timeout):
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        pass


class ArticleListApiView(generics.GenericAPIView):
    serializer_class = ArticleSerializer
    permission_classes = [AllowAny]
    pagination_class = CustomRestPagination

    def __init__(self, **kwargs):
        self.response_format = ResponseInfo().response
        super(ArticleListApiView, self).__init__(**kwargs)

    def get_queryset(self):
        queryset = (
            Article.objects
            .select_related('author')
            .only(
                'id',
                'title',
                'slug',
                'short_description',
                'content',
                'featured_image',
                'author_id',
                'author__username',
                'status',
                'is_featured',
                'views_count',
                'published_at',
                'created_at',
                'updated_at',
            )
            .order_by('-published_at', '-id')
        )

        status_filter = self.request.query_params.get('status')
        featured_filter = self.request.query_params.get('is_featured')
        search = self.request.query_params.get('search')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if featured_filter is not None:
            queryset = queryset.filter(is_featured=featured_filter.lower() in ['1', 'true', 'yes'])

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(short_description__icontains=search) |
                Q(content__icontains=search)
            )

        return queryset

    def get_cache_key(self, request):
        version = get_cache_value(ARTICLE_CACHE_VERSION_KEY, 1)
        normalized_params = {
            key: request.query_params.getlist(key)
            for key in sorted(request.query_params.keys())
        }
        params_hash = hashlib.md5(json.dumps(normalized_params, sort_keys=True).encode()).hexdigest()
        return f'articles:list:v{version}:{params_hash}'

    @swagger_auto_schema(
        tags=["Articles"],
        operation_id='articles-list',
        operation_description="List articles with pagination, optional filters, and cache-backed responses.",
        manual_parameters=[
            openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER),
            openapi.Parameter('limit', openapi.IN_QUERY, description='Items per page', type=openapi.TYPE_INTEGER),
            openapi.Parameter('status', openapi.IN_QUERY, description='draft, published, or archived', type=openapi.TYPE_STRING),
            openapi.Parameter('is_featured', openapi.IN_QUERY, description='true or false', type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('search', openapi.IN_QUERY, description='Search title, short description, and content', type=openapi.TYPE_STRING),
        ],
    )
    def get(self, request):
        try:
            cache_key = self.get_cache_key(request)
            cached_response = get_cache_value(cache_key)
            if cached_response:
                return Response(cached_response, status=status.HTTP_200_OK)

            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            serializer = self.serializer_class(page, many=True, context={'request': request})
            paginated_data = self.paginator.get_paginated_response(serializer.data)

            response_format = deepcopy(self.response_format)
            response_format['status_code'] = status.HTTP_200_OK
            response_format['status'] = True
            response_format['message'] = _success
            response_format['data'] = paginated_data

            set_cache_value(cache_key, response_format, timeout=ARTICLE_LIST_CACHE_TIMEOUT)
            return Response(response_format, status=status.HTTP_200_OK)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            self.response_format['status_code'] = status.HTTP_500_INTERNAL_SERVER_ERROR
            self.response_format['status'] = False
            self.response_format['message'] = f'exc_type : {exc_type},fname : {fname},tb_lineno : {exc_tb.tb_lineno},error : {str(e)}'
            return Response(self.response_format, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
