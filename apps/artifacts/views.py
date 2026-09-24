import uuid
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apps.artifacts.minio_client import generate_presigned_upload_url
from apps.artifacts.models import Artifact
from apps.projects.models import ProjectVersion

@csrf_exempt
@require_POST
def get_upload_url(request):
    try:
        data = json.loads(request.body)
        original_filename = data.get('original_filename')
        
        if not original_filename:
            return JsonResponse({'error': 'original_filename is required'}, status=400)
            
        storage_key = str(uuid.uuid4())
        url = generate_presigned_upload_url(storage_key)
        
        return JsonResponse({
            'url': url,
            'storage_key': storage_key
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def confirm_upload(request):
    try:
        data = json.loads(request.body)
        storage_key = data.get('storage_key')
        original_filename = data.get('original_filename')
        size_bytes = data.get('size_bytes')
        sha256 = data.get('sha256')
        project_version_id = data.get('project_version_id')

        # Thêm các field tuỳ chọn nếu có
        artifact_type = data.get('artifact_type', 'UNKNOWN')
        content_type = data.get('content_type', '')

        if not all([storage_key, original_filename, size_bytes, sha256, project_version_id]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
            
        try:
            project_version = ProjectVersion.objects.get(id=project_version_id)
        except ProjectVersion.DoesNotExist:
            return JsonResponse({'error': 'ProjectVersion not found'}, status=404)

        # Deduplication logic
        existing_artifact = Artifact.objects.filter(sha256=sha256).first()
        if existing_artifact:
            # Trỏ storage_key của record mới về storage_key của Artifact cũ
            final_storage_key = existing_artifact.storage_key
        else:
            final_storage_key = storage_key

        # Insert bản ghi mới với trạng thái PENDING
        artifact = Artifact.objects.create(
            project_version=project_version,
            artifact_type=artifact_type,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=sha256,
            storage_key=final_storage_key,
            status='PENDING'
        )
        
        # Trigger Celery Task để chạy Pre-check
        from apps.artifacts.tasks import run_artifact_precheck
        run_artifact_precheck.delay(str(artifact.id))
        
        return JsonResponse({
            'message': 'Upload confirmed successfully',
            'artifact_id': str(artifact.id),
            'storage_key': final_storage_key,
            'deduplicated': existing_artifact is not None
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
