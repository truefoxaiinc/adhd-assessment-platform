from pathlib import Path

import firebase_admin
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from firebase_admin import credentials


def initialize_firebase():
    if not settings.FIREBASE_INITIALIZE:
        return None

    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    credentials_path = settings.FIREBASE_CREDENTIALS_PATH
    if credentials_path:
        path = Path(credentials_path)
        if not path.is_file():
            raise ImproperlyConfigured(
                'FIREBASE_CREDENTIALS_PATH does not point to a readable file'
            )
        return firebase_admin.initialize_app(credentials.Certificate(str(path)))

    # Uses GOOGLE_APPLICATION_CREDENTIALS or the runtime's attached identity.
    return firebase_admin.initialize_app()
