from rest_framework import serializers
from apps.articles.models import Article


class ArticleSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)
    featured_image = serializers.ImageField(read_only=True)

    class Meta:
        model = Article
        fields = [
            'id',
            'title',
            'slug',
            'short_description',
            'content',
            'featured_image',
            'author',
            'author_name',
            'status',
            'is_featured',
            'views_count',
            'published_at',
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        title = attrs.get('title', '')
        if not title:
            raise serializers.ValidationError("Title is required.")
        return super().validate(attrs)
    
    
