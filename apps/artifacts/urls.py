from django.urls import path
from . import views

urlpatterns = [
    path('upload-url/', views.get_upload_url, name='get_upload_url'),
    path('confirm-upload/', views.confirm_upload, name='confirm_upload'),
]
