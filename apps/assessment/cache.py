import hashlib
import json

from django.core.cache import cache


ASSESSMENT_CACHE_TIMEOUT = 60 * 15
QUESTIONS_CACHE_VERSION_KEY = 'assessment:questions:version'
RESULT_CACHE_VERSION_KEY_TEMPLATE = 'assessment:result:user:{user_id}:version'
MANAGEMENT_WEEK_DETAILS_VERSION_KEY_TEMPLATE = 'assessment:management:week-details:user:{user_id}:version'


def cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception:
        return default


def cache_set(key, value, timeout=ASSESSMENT_CACHE_TIMEOUT):
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        pass


def bump_cache_version(key):
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 2, timeout=None)
    except Exception:
        pass


def get_questions_cache_key(request, is_for_adults):
    version = cache_get(QUESTIONS_CACHE_VERSION_KEY, 1)
    normalized_params = {
        key: request.query_params.getlist(key)
        for key in sorted(request.query_params.keys())
    }
    params_hash = hashlib.md5(json.dumps(normalized_params, sort_keys=True).encode()).hexdigest()
    return f'assessment:questions:v{version}:adult:{is_for_adults}:{params_hash}'


def get_result_cache_key(user_id):
    version_key = RESULT_CACHE_VERSION_KEY_TEMPLATE.format(user_id=user_id)
    version = cache_get(version_key, 1)
    return f'assessment:result:user:{user_id}:v{version}:latest'


def get_progress_cache_key(user_id, is_for_adults):
    questions_version = cache_get(QUESTIONS_CACHE_VERSION_KEY, 1)
    result_version_key = RESULT_CACHE_VERSION_KEY_TEMPLATE.format(user_id=user_id)
    result_version = cache_get(result_version_key, 1)
    return f'assessment:progress:user:{user_id}:adult:{is_for_adults}:qv{questions_version}:rv{result_version}'


def get_management_week_details_cache_key(user_id, request):
    version_key = MANAGEMENT_WEEK_DETAILS_VERSION_KEY_TEMPLATE.format(user_id=user_id)
    version = cache_get(version_key, 1)
    normalized_params = {
        key: request.query_params.getlist(key)
        for key in sorted(request.query_params.keys())
    }
    params_hash = hashlib.md5(json.dumps(normalized_params, sort_keys=True).encode()).hexdigest()
    return f'assessment:management:week-details:user:{user_id}:v{version}:{params_hash}'


def bump_user_result_cache(user_id):
    if user_id:
        bump_cache_version(RESULT_CACHE_VERSION_KEY_TEMPLATE.format(user_id=user_id))


def bump_user_management_cache(user_id):
    if user_id:
        bump_cache_version(MANAGEMENT_WEEK_DETAILS_VERSION_KEY_TEMPLATE.format(user_id=user_id))
