from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class PublicMediaStorage(S3Boto3Storage):
    location = settings.AWS_LOCATION
    default_acl = None
    file_overwrite = False
    querystring_auth = False


class PrivateMediaStorage(S3Boto3Storage):
    location = getattr(settings, "AWS_PRIVATE_MEDIA_LOCATION", "private")
    default_acl = None
    file_overwrite = False
    querystring_auth = True


class LargeMediaStorage(PublicMediaStorage):
    """Storage backend for large admin-uploaded videos."""

    querystring_auth = True
    object_parameters = {
        "CacheControl": "max-age=86400",
    }


class ArticleImageStorage(PublicMediaStorage):
    """Public image storage used by the staff-only article editor."""

    location = f"{settings.AWS_LOCATION}/adhd_content/articles"
    object_parameters = {
        "CacheControl": "max-age=31536000, immutable",
    }
