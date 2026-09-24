from django.urls import path
from . import views

urlpatterns = [
    path('overview/', views.overview_view, name='overview'),
    path('projects/', views.project_list_view, name='project_list'),
    path('projects/new/', views.project_form_view, name='project_form'),
    path('api/projects/create/', views.create_project, name='create_project'),
    path('projects/<uuid:project_id>/', views.project_detail_view, name='project_detail'),
    # for simplicity, string can be used for mock id
    path('projects/<str:project_id>/', views.project_detail_view, name='project_detail_str'),
    path('projects/<uuid:project_id>/delete/', views.delete_project_view, name='delete_project'),
    path('projects/<uuid:project_id>/edit/', views.project_edit_view, name='project_edit'),
    path('api/projects/<uuid:project_id>/update/', views.update_project_api, name='update_project_api'),
    path('projects/<uuid:project_id>/settings/', views.update_project_settings, name='update_project_settings'),
]
