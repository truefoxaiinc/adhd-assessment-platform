import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_adhd.settings")

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from apps.websocket import routing
from apps.websocket.middleware import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(routing.websocket_urlpatterns)
    ),
})