from django.contrib import admin
from .models import Article
# Register your models here.


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "author", "status", "published_at", "created_at")
    list_filter = ("status", "is_featured", "published_at")
    search_fields = ("title", "author__username")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("views_count",)
    fieldsets = (
        (None, {
            "fields": ("title", "slug", "short_description", "content", "featured_image")
        }),
        ("Publication Info", {
            "fields": ("author", "status", "is_featured", "published_at")
        }),
        ("Metadata", {
            "fields": ("views_count",)
        }),
    )

