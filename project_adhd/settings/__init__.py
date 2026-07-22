import os


DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development').lower()

if DJANGO_ENV in {'prod', 'production'}:
    from project_adhd.settings.prod import *  # noqa: F401,F403
elif DJANGO_ENV == 'test':
    from project_adhd.settings.test import *  # noqa: F401,F403
else:
    from project_adhd.settings.dev import *  # noqa: F401,F403
