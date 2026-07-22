from project_adhd.settings.base import *  # noqa: F401,F403

DEBUG = False if IS_PRODUCTION else get_env_value('DEBUG', True)

if DEBUG and not IS_PRODUCTION:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(
        MIDDLEWARE.index('django.middleware.csrf.CsrfViewMiddleware'),
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )
