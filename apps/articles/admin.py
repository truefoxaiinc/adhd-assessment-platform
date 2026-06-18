from django.contrib import admin
from django.utils.html import format_html
from .models import Article
# Register your models here.


from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.import_export.forms import ExportForm, ImportForm

@admin.register(Article)
class ArticleAdmin(ModelAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = ExportForm

    list_display = ("id", "title", "author", "status_badge", "featured_badge", "views_count", "published_at", "created_at")
    list_filter = ("status", "is_featured", "published_at")
    search_fields = ("title", "author__username")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("views_count", "created_at", "updated_at")
    date_hierarchy = "published_at"
    ordering = ("-created_at",)
    list_per_page = 25

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            "published": "text-green-700",
            "draft": "text-amber-700",
            "archived": "text-slate-500",
        }
        return format_html(
            '<span class="{} font-semibold">{}</span>',
            colors.get(obj.status, "text-slate-600"),
            obj.get_status_display(),
        )

    @admin.display(description="Featured", boolean=True, ordering="is_featured")
    def featured_badge(self, obj):
        return obj.is_featured
    fieldsets = (
        (None, {
            "fields": ("title", "slug", "short_description", "content", "featured_image")
        }),
        ("Publication Info", {
            "fields": ("author", "status", "is_featured", "published_at")
        }),
        ("Metadata", {
            "fields": ("views_count", "created_at", "updated_at")
        }),
    )

