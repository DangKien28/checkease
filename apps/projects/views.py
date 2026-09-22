from django.shortcuts import render

def overview_view(request):
    return render(request, 'pages/overview.html', {'total_projects': 0, 'running_count': 0, 'pass_count': 0, 'avg_score': "0.0", 'projects': [], 'recent_projects': []})

def project_list_view(request):
    return render(request, 'pages/project_list.html', {'projects': []})

def project_detail_view(request, project_id):
    return render(request, 'pages/project_detail.html', {'project_id': project_id})

def project_form_view(request):
    return render(request, 'pages/project_form.html')
