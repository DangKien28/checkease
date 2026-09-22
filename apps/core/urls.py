from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('settings/', views.settings_view, name='settings'),
]
