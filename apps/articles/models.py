from django.db import models

# Create your models here.
from django.utils.text import slugify
from helpers.abstract_models import AbstractDateFieldMix
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Article(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    )

    title                 = models.CharField(max_length=255)
    slug                  = models.SlugField(unique=True, blank=True)
    short_description     = models.TextField(blank=True)
    content               = models.TextField()
    featured_image        = models.ImageField(upload_to="articles/",blank=True,null=True)
    author                = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,related_name="articles")
    status                = models.CharField(max_length=20,choices=STATUS_CHOICES,default="draft",db_index=True)
    is_featured           = models.BooleanField(default=False,db_index=True)
    views_count           = models.PositiveIntegerField(default=0)
    published_at          = models.DateTimeField(blank=True,null=True)
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "articles"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["published_at"]),
            models.Index(fields=["status", "-published_at", "-id"]),
            models.Index(fields=["status", "is_featured", "-published_at", "-id"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            while Article.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
