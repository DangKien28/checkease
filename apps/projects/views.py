import json
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import render
from apps.projects.models import Project, ProjectVersion

from django.contrib.auth.decorators import login_required

@login_required(login_url='/login/')
def overview_view(request):
    user_projects = Project.objects.filter(owner_id=request.user.id)
    total_projects = user_projects.count()
    recent_projects_db = user_projects.order_by('-created_at')[:5]
    
    recent_projects = []
    for p in recent_projects_db:
        # Tạm tính tier
        tier_val = 2
        if p.application_tier and '1' in p.application_tier: tier_val = 1
        elif p.application_tier and '3' in p.application_tier: tier_val = 3
        
        recent_projects.append({
            'id': str(p.id),
            'name': p.name,
            'tier': tier_val,
            'verdict': 'unknown',
            'time_ago': 'Vừa xong'
        })
        
    return render(request, 'pages/overview.html', {
        'total_projects': total_projects,
        'running_count': 0, # Tạm thời chưa móc
        'pass_count': 0, 
        'avg_score': "0.0",
        'projects': [],
        'recent_projects': recent_projects,
        'user': request.user
    })

@login_required(login_url='/login/')
def project_list_view(request):
    projects_db = Project.objects.filter(owner_id=request.user.id).order_by('-created_at')
    projects_context = []
    for p in projects_db:
        # Lấy thông tin cơ bản để hiển thị theo HTML cũ
        tier_val = 2
        if p.application_tier and '1' in p.application_tier: tier_val = 1
        elif p.application_tier and '3' in p.application_tier: tier_val = 3
        
        projects_context.append({
            'id': str(p.id),
            'name': p.name,
            'description': p.description or 'Chưa có mô tả',
            'tier': tier_val,
            'w_testing': f"{float(p.testing_weight*100):.0f}%",
            'w_code': f"{float(p.source_code_weight*100):.0f}%",
            'latest_run': False # Tạm thời chưa móc sang bảng AnalysisRun
        })
    return render(request, 'pages/project_list.html', {'projects': projects_context})

from django.shortcuts import render, get_object_or_404
@login_required(login_url='/login/')
def project_detail_view(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner_id=request.user.id)
    latest_version = ProjectVersion.objects.filter(project=project).order_by('-version_number').first()
    v_num = latest_version.version_number if latest_version else 1
    
    tier_val = 2
    if project.application_tier and '1' in project.application_tier: tier_val = 1
    elif project.application_tier and '3' in project.application_tier: tier_val = 3

    context = {
        'project': project,
        'v_num': v_num,
        'tier_val': tier_val,
        'w_testing': float(project.testing_weight),
        'w_code': float(project.source_code_weight),
        'pass_th': float(project.pass_threshold),
        'warn_th': float(project.warning_threshold)
    }
    return render(request, 'pages/project_detail.html', context)

@login_required(login_url='/login/')
def project_form_view(request):
    return render(request, 'pages/project_form.html')

@csrf_exempt
@require_POST
def create_project(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', 'Dự án mới')
        description = data.get('description', '')
        
        # UUID từ người dùng đã đăng nhập
        owner_id = request.user.id
        
        project = Project.objects.create(
            owner_id=owner_id,
            name=name,
            description=description,
            application_tier=f"Tier {data.get('tier', '3')}",
            testing_weight=Decimal('0.5'),
            source_code_weight=Decimal('0.5'),
            pass_threshold=Decimal('80.0'),
            warning_threshold=Decimal('60.0')
        )
        
        project_version = ProjectVersion.objects.create(
            project=project,
            version_number=1,
            status='DRAFT'
        )
        
        return JsonResponse({
            'project_id': str(project.id),
            'project_version_id': str(project_version.id)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

import json
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apps.projects.models import Project

@csrf_exempt
@require_POST
def update_project_settings(request, project_id):
    try:
        data = json.loads(request.body)
        
        try:
            testing_weight = Decimal(str(data.get('testing_weight', 0)))
            source_code_weight = Decimal(str(data.get('source_code_weight', 0)))
            pass_threshold = Decimal(str(data.get('pass_threshold', 0)))
            warning_threshold = Decimal(str(data.get('warning_threshold', 0)))
        except (InvalidOperation, TypeError, ValueError):
            return JsonResponse({"error": "Lỗi: Dữ liệu weight hoặc threshold không hợp lệ (phải là số)."}, status=400)
            
        application_tier = data.get('application_tier')

        if (testing_weight + source_code_weight) != Decimal('1.00'):
            return JsonResponse({"error": "Lỗi: Tổng testing_weight và source_code_weight phải bằng chính xác 1.00"}, status=400)

        if pass_threshold <= warning_threshold:
            return JsonResponse({"error": "Ngưỡng Pass phải lớn hơn ngưỡng Warning"}, status=400)

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return JsonResponse({"error": "Không tìm thấy project với ID này."}, status=404)

        project.testing_weight = testing_weight
        project.source_code_weight = source_code_weight
        project.pass_threshold = pass_threshold
        project.warning_threshold = warning_threshold
        
        if application_tier is not None:
            project.application_tier = application_tier
            
        project.save()

        return JsonResponse({"message": "Cập nhật cấu hình Project thành công."}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Định dạng JSON không hợp lệ."}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Lỗi hệ thống: {str(e)}"}, status=500)

from django.http import HttpResponse
@login_required(login_url='/login/')
def delete_project_view(request, project_id):
    if request.method in ['POST', 'DELETE']:
        project = get_object_or_404(Project, id=project_id, owner_id=request.user.id)
        project.delete() # Or sp_soft_delete_project if soft delete is preferred
        return HttpResponse('') # HTMX hx-swap="outerHTML" will remove the row
    return HttpResponse(status=405)

@login_required(login_url='/login/')
def project_edit_view(request, project_id):
    project = get_object_or_404(Project, id=project_id, owner_id=request.user.id)
    
    tier_val = 3
    if project.application_tier and '1' in project.application_tier: tier_val = 1
    elif project.application_tier and '2' in project.application_tier: tier_val = 2
    
    return render(request, 'pages/project_edit.html', {
        'project': project,
        'tier_val': tier_val
    })

@csrf_exempt
@require_POST
def update_project_api(request, project_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
        
    try:
        project = get_object_or_404(Project, id=project_id, owner_id=request.user.id)
        data = json.loads(request.body)
        
        if 'name' in data: project.name = data['name']
        if 'description' in data: project.description = data['description']
        if 'tier' in data: project.application_tier = f"Tier {data['tier']}"
        
        project.save()
        
        return JsonResponse({
            'message': 'Đã cập nhật dự án thành công',
            'project_id': str(project.id)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
