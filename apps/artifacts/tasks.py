import os
import tempfile
from celery import shared_task
from django.utils import timezone
from apps.artifacts.models import Artifact
from apps.artifacts.minio_client import download_artifact
from apps.gate_engine.pre_check import ArtifactPreChecker

@shared_task
def run_artifact_precheck(artifact_id):
    try:
        artifact = Artifact.objects.get(id=artifact_id)
        
        # Đánh dấu đang xử lý
        artifact.status = 'VALIDATING'
        artifact.save()

        # Tạo file tạm để tải từ MinIO về
        _, temp_path = tempfile.mkstemp(suffix='.zip')
        
        try:
            download_artifact(artifact.storage_key, temp_path)
            
            checker = ArtifactPreChecker()
            result = checker.run_check(temp_path)
            
            if result.get("is_valid"):
                artifact.status = 'VALIDATED'
                artifact.validated_at = timezone.now()
            else:
                artifact.status = 'FAILED'
                artifact.error_code = result.get("error_code")
                artifact.error_message = result.get("error_message")
                
            artifact.save()
            
        finally:
            # Dọn dẹp file tạm
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Artifact.DoesNotExist:
        pass
    except Exception as e:
        # Bắt lỗi bất ngờ trong quá trình download/validate
        try:
            artifact.status = 'FAILED'
            artifact.error_code = 'SYSTEM_ERROR'
            artifact.error_message = str(e)
            artifact.save()
        except:
            pass
