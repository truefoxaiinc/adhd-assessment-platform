from project_adhd.settings.base import *  # noqa: F401,F403

DEBUG = False
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
