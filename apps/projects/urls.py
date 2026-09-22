from django.urls import path
from . import views

urlpatterns = [
    path('overview/', views.overview_view, name='overview'),
    path('projects/', views.project_list_view, name='project_list'),
    path('projects/new/', views.project_form_view, name='project_form'),
    path('projects/<uuid:project_id>/', views.project_detail_view, name='project_detail'),
    # for simplicity, string can be used for mock id
    path('projects/<str:project_id>/', views.project_detail_view, name='project_detail_str'),
]
