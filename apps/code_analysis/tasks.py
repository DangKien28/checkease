import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.code_analysis.pipeline import run_code_analysis
from apps.code_analysis.scoring import DEFAULT_RULE_PENALTY_CAP
from apps.gate_engine.models import AnalysisResult, AnalysisRun

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue="queue_sast", soft_time_limit=300, time_limit=330)
def start_sast_scan(self, analysis_run_id):
    """Task SAST — chạy trên queue_sast riêng, idempotent theo run_id."""
    try:
        run = AnalysisRun.objects.get(id=analysis_run_id)
    except AnalysisRun.DoesNotExist:
        logger.warning("start_sast_scan: không tìm thấy AnalysisRun %s", analysis_run_id)
        return

    if run.status == "IN_PROGRESS":
        logger.info("start_sast_scan: run %s đang chạy, bỏ qua", analysis_run_id)
        return

    run.status = "IN_PROGRESS"
    if run.started_at is None:
        run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])

    try:
        # TODO: lấy thư mục đã giải nén an toàn từ Artifact (SOURCE_ZIP, VALID)
        target_dir = getattr(settings, "CODE_SCAN_TARGET_DIR", ".")
        result = run_code_analysis(
            target_dir,
            secret_allowlist=getattr(settings, "CODE_SECRET_ALLOWLIST", None) or None,
            rule_penalty_cap=getattr(settings, "CODE_RULE_PENALTY_CAP", DEFAULT_RULE_PENALTY_CAP),
            pass_threshold=getattr(settings, "CODE_PASS_THRESHOLD", None),
            warning_threshold=getattr(settings, "CODE_WARNING_THRESHOLD", None),
        )

        # Idempotent: chạy lại cùng run_id thì cập nhật, không tạo bản ghi trùng
        AnalysisResult.objects.update_or_create(
            analysis_run=run,
            defaults={
                "source_code_score": result.code_score,
                "findings": result.to_dict(),
                "metadata": {"branch": "code", "schema_version": "1.0"},
            },
        )
        run.status = "COMPLETED"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
        logger.info(
            "start_sast_scan: run %s xong (score=%s, hard_gate=%s, warnings=%d)",
            analysis_run_id, result.code_score, result.hard_gate_triggered,
            len(result.warnings),
        )
    except Exception:
        logger.exception("start_sast_scan: lỗi khi chạy run %s", analysis_run_id)
        run.status = "FAILED"
        run.save(update_fields=["status"])
        raise
