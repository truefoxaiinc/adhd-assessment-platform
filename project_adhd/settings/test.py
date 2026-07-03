from project_adhd.settings.base import *  # noqa: F401,F403

DEBUG = False
if config('USE_SQLITE_FOR_TESTS', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'test.sqlite3',
        }
    }

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]
CELERY_TASK_ALWAYS_EAGER = True
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'adhd-test-cache',
    }
}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
