from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('settings/', views.settings_view, name='settings'),
    path('api/settings/update/', views.update_global_settings, name='update_global_settings'),
]
