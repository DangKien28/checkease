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
        
        # ÄÃ¡nh dáº¥u Ä‘ang xá»­ lÃ½
        artifact.status = 'VALIDATING'
        artifact.save()

        # Táº¡o file táº¡m Ä‘á»ƒ táº£i tá»« MinIO vá»
        from django.conf import settings
        project_tmp_dir = os.path.join(settings.BASE_DIR, 'tmp')
        os.makedirs(project_tmp_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(suffix='.zip', dir=project_tmp_dir)
        os.close(fd)
        
        try:
            download_artifact(artifact.storage_key, temp_path)
            
            # Run prechecker if it's source code (ZIP)
            # Testing documents (PDF, XML, etc.) might not be zip files.
            is_testing_doc = artifact.artifact_type in ['TEST_DOC', 'TEST_DOCUMENT', 'TESTING', 'TEST_CASE', 'TEST_RESULT']
            
            if is_testing_doc:
                # Bypass zip pre-check for testing documents since they can be pdf, xml, etc.
                artifact.status = 'VALIDATED'
                artifact.validated_at = timezone.now()
                artifact.save()
                
                # Trigger testing analysis workflow
                from apps.testing_analysis.tasks import process_testing_document
                process_testing_document.delay(str(artifact.id))
            else:
                checker = ArtifactPreChecker()
                result = checker.run_check(temp_path)
                
                if result.get("is_valid"):
                    artifact.status = 'VALIDATED'
                    artifact.validated_at = timezone.now()
                    artifact.save()
                    
                    # Trigger Source Code Analysis workflow
                    from apps.code_analysis.tasks import start_sast_scan
                    start_sast_scan.delay(str(artifact.id))
                else:
                    artifact.status = 'FAILED'
                    artifact.error_code = result.get("error_code")
                    artifact.error_message = result.get("error_message")
                    artifact.save()
            
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    except Artifact.DoesNotExist:
        pass
    except Exception as e:
        # Báº¯t lá»—i báº¥t ngá» trong quÃ¡ trÃ¬nh download/validate
        try:
            artifact.status = 'FAILED'
            artifact.error_code = 'SYSTEM_ERROR'
            import traceback
            artifact.error_message = traceback.format_exc()
            artifact.save()
        except:
            pass


