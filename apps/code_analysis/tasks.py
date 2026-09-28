import os
import shutil
import zipfile
import tempfile
from celery import shared_task
from django.utils import timezone
from apps.projects.models import ProjectVersion
from apps.artifacts.models import Artifact
from apps.artifacts.minio_client import download_artifact
from apps.code_analysis.pipeline import run_code_analysis
from apps.code_analysis.models import SourceCodeResultModel

@shared_task
def start_sast_scan(artifact_id):
    try:
        artifact = Artifact.objects.get(id=artifact_id)
        project_version = artifact.project_version
        
        result_record, created = SourceCodeResultModel.objects.get_or_create(
            project_version=project_version,
            artifact=artifact,
            defaults={'status': 'PROCESSING'}
        )
        if not created:
            result_record.status = 'PROCESSING'
            result_record.save()
            
        from django.conf import settings
        project_tmp_dir = os.path.join(settings.BASE_DIR, 'tmp')
        os.makedirs(project_tmp_dir, exist_ok=True)
        
        temp_dir = tempfile.mkdtemp(prefix="checkease_source_", dir=project_tmp_dir)
        zip_path = os.path.join(temp_dir, "source.zip")
        
        try:
            download_artifact(artifact.storage_key, zip_path)
            
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(extract_dir)
                
            # Chạy toàn bộ pipeline SAST với cấu hình ngưỡng của dự án
            proj = project_version.project
            p_th = float(proj.pass_threshold) if proj.pass_threshold else 80.0
            w_th = float(proj.warning_threshold) if proj.warning_threshold else 60.0
            code_result = run_code_analysis(extract_dir, pass_threshold=p_th, warning_threshold=w_th)
            
            result_record.code_score = code_result.code_score
            result_record.hard_gate_triggered = code_result.hard_gate_triggered
            result_record.result_json = code_result.to_dict()
            result_record.status = 'COMPLETED'
            result_record.save()
            
            from apps.gate_engine.orchestrator import check_and_aggregate
            check_and_aggregate(project_version.id)
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        try:
            result_record.status = 'FAILED'
            result_record.error_message = str(e)
            result_record.save()
        except:
            pass
