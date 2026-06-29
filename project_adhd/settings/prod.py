from project_adhd.settings.base import *  # noqa: F401,F403

DEBUG = False
SECURE_SSL_REDIRECT = get_env_value('SECURE_SSL_REDIRECT', True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
