from django.urls import path, include

urlpatterns = [
    path('', include('apps.core.urls')),
    path('', include('apps.accounts.urls')),
    path('', include('apps.projects.urls')),
    path('api/artifacts/', include('apps.artifacts.urls')),
    path('api/v1/gate/', include('apps.gate_engine.urls')),
]
