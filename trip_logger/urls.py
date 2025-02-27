from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view  # type: ignore
from drf_yasg import openapi  # type: ignore


# Swagger/OpenAPI schema configuration
schema_view = get_schema_view(
    openapi.Info(
        title="Trip Planner API",
        default_version="v1",
        description="API for trip route planning and ELD logs",
        terms_of_service="https://www.example.com/terms/",
        contact=openapi.Contact(email="support@example.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

# URL patterns for the app
urlpatterns = [
    # Admin panel (not used though)
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/', include('app.urls')),

    # Swagger UI
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),

    # ReDoc UI
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Raw JSON/YAML API Schema
    path('swagger.json/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
]