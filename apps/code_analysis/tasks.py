import logging
import time

from celery import shared_task

from apps.code_analysis.pipeline import run_code_analysis
from apps.gate_engine.models import AnalysisResult, AnalysisRun

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue="queue_sast", soft_time_limit=300, time_limit=330)
def start_sast_scan(self, analysis_run_id):
    """Task SAST — chạy trên queue_sast riêng, idempotent theo run_id."""
    try:
        run = AnalysisRun.objects.get(id=analysis_run_id)
    except AnalysisRun.DoesNotExist:
        logger.warning("start_sast_scan: AnalysisRun %s not found", analysis_run_id)
        return

    if run.status == "IN_PROGRESS":
        logger.info("start_sast_scan: run %s already in progress, skip", analysis_run_id)
        return

    run.status = "IN_PROGRESS"
    run.started_at = run.started_at or time.time()
    run.save(update_fields=["status", "started_at"])

    try:
        # TODO: lấy thư mục target đã giải nén an toàn từ Artifact (SOURCE_ZIP, trạng thái VALID)
        target_dir = "."
        result = run_code_analysis(target_dir)

        AnalysisResult.objects.update_or_create(
            analysis_run=run,
            defaults={
                "source_code_score": result.code_score,
                "findings": {
                    "hard_gate_triggered": result.hard_gate_triggered,
                    "score_breakdown": result.score_breakdown,
                    "counts": result.counts,
                    "findings": result.findings,
                    "scan_meta": result.scan_meta,
                    "warnings": result.warnings,
                    "status": result.status,
                },
                "metadata": {"branch": "code", "schema_version": "1.0"},
            },
        )
        run.status = "COMPLETED"
        run.finished_at = time.time()
        run.save(update_fields=["status", "finished_at"])
    except Exception:
        logger.exception("start_sast_scan: failed for run %s", analysis_run_id)
        run.status = "FAILED"
        run.save(update_fields=["status"])
        raise
