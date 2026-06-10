from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Article


ARTICLE_CACHE_VERSION_KEY = 'articles:list:version'


def bump_article_cache_version():
    try:
        cache.incr(ARTICLE_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(ARTICLE_CACHE_VERSION_KEY, 2, timeout=None)
    except Exception:
        pass


@receiver(post_save, sender=Article)
def clear_article_cache_on_save(sender, instance, **kwargs):
    bump_article_cache_version()


@receiver(post_delete, sender=Article)
def clear_article_cache_on_delete(sender, instance, **kwargs):
    bump_article_cache_version()
