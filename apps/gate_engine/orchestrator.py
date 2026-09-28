import logging
from django.utils import timezone
from apps.projects.models import ProjectVersion
from apps.gate_engine.models import AnalysisRun, AnalysisResult
from apps.code_analysis.models import SourceCodeResultModel
from apps.testing_analysis.models import TestingResultModel
from apps.gate_engine.aggregator import GateEngine

logger = logging.getLogger(__name__)

def check_and_aggregate(project_version_id):
    """
    Called whenever a branch (code or testing) finishes.
    Creates or updates the AnalysisRun and AnalysisResult.
    """
    try:
        pv = ProjectVersion.objects.get(id=project_version_id)
        project = pv.project
        
        # 1. Get or Create active AnalysisRun
        run, created = AnalysisRun.objects.get_or_create(
            project_version=pv,
            status__in=['PENDING', 'PROCESSING'],
            defaults={
                'status': 'PROCESSING',
                'testing_weight_snapshot': project.testing_weight,
                'source_code_weight_snapshot': project.source_code_weight,
                'pass_threshold_snapshot': project.pass_threshold,
                'warning_threshold_snapshot': project.warning_threshold,
                'started_at': timezone.now()
            }
        )
        
        # 2. Get or Create AnalysisResult
        result, _ = AnalysisResult.objects.get_or_create(analysis_run=run)
        
        # 3. Pull latest scores from the branches
        latest_code = SourceCodeResultModel.objects.filter(project_version=pv).order_by('-created_at').first()
        latest_test = TestingResultModel.objects.filter(project_version=pv).order_by('-created_at').first()
        
        code_score = float(latest_code.code_score) if latest_code and latest_code.status == 'COMPLETED' and latest_code.code_score is not None else None
        test_score = float(latest_test.testing_score) if latest_test and latest_test.status == 'COMPLETED' and latest_test.testing_score is not None else None
        
        result.source_code_score = code_score
        result.testing_score = test_score
        
        has_critical = False
        if latest_code and latest_code.hard_gate_triggered:
            has_critical = True
        if latest_test and latest_test.result_json and latest_test.result_json.get('critical_count', 0) > 0:
            has_critical = True
            
        is_finished = False
        if (latest_code and latest_code.status == 'COMPLETED') and (latest_test and latest_test.status == 'COMPLETED'):
            is_finished = True
        elif (latest_code and latest_code.status == 'FAILED') or (latest_test and latest_test.status == 'FAILED'):
            is_finished = True
            
        # Only compute final score if we have some score. If a branch hasn't uploaded, it's 0.0 temporarily.
        try:
            engine = GateEngine(w_test=float(run.testing_weight_snapshot), w_code=float(run.source_code_weight_snapshot), pass_threshold=float(run.pass_threshold_snapshot), warning_threshold=float(run.warning_threshold_snapshot))
            errors = [{"severity": "Critical"}] if has_critical else []
            gate_result = engine.evaluate(
                test_score=test_score if test_score is not None else 0.0,
                code_score=code_score if code_score is not None else 0.0,
                errors=errors
            )
            result.final_score = gate_result.score
            result.decision = gate_result.verdict
        except Exception as e:
            logger.error(f"GateEngine error: {e}")
            
        result.save()
        
        if is_finished:
            run.status = 'COMPLETED'
            run.finished_at = timezone.now()
            run.save()
            
    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
