import time
from celery import shared_task
from apps.gate_engine.models import AnalysisRun

@shared_task
def start_sast_scan(analysis_run_id):
    try:
        run = AnalysisRun.objects.get(id=analysis_run_id)
        
        # Cập nhật trạng thái thành IN_PROGRESS
        run.status = 'IN_PROGRESS'
        run.save()
        
        # Giả lập quá trình quét mất 5 giây
        time.sleep(5)
        
        # Hoàn thành quét
        run.status = 'COMPLETED'
        run.save()
        
    except AnalysisRun.DoesNotExist:
        pass
