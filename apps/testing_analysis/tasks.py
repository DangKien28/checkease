import os
import tempfile
from celery import shared_task
from django.utils import timezone
from apps.projects.models import ProjectVersion
from apps.artifacts.models import Artifact
from apps.artifacts.minio_client import download_artifact
from apps.testing_analysis.parsers import get_parser
from apps.testing_analysis.rule_based_analyzer import RuleBasedAnalyzer
from apps.testing_analysis.ai_semantic_analyzer import AISemanticAnalyzer
from apps.testing_analysis.scoring_engine import ScoringEngine
from apps.testing_analysis.models import TestingResultModel
from dataclasses import asdict

@shared_task
def process_testing_document(artifact_id):
    try:
        artifact = Artifact.objects.get(id=artifact_id)
        project_version = artifact.project_version
        
        result_record, created = TestingResultModel.objects.get_or_create(
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
        fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(artifact.original_filename)[1], dir=project_tmp_dir)
        os.close(fd)
        
        try:
            download_artifact(artifact.storage_key, temp_path)
            
            # Giai Ä‘oáº¡n 2 & 3: PhÃ¢n tÃ­ch & Chuáº©n hÃ³a
            parser = get_parser(artifact.original_filename)
            records = parser.parse(temp_path)
            
            # Giai Ä‘oáº¡n 4: Hybrid Analyzer
            rule_analyzer = RuleBasedAnalyzer()
            completed, needs_ai = rule_analyzer.analyze(records)
            
            if needs_ai:
                ai_analyzer = AISemanticAnalyzer()
                ai_records = ai_analyzer.analyze_defects(needs_ai)
                records = completed + ai_records
            else:
                records = completed
                
            # Giai Ä‘oáº¡n 5: TÃ­nh Ä‘iá»ƒm
            scoring_engine = ScoringEngine()
            testing_result = scoring_engine.calculate(records)
            
            # Giai Ä‘oáº¡n 6: Nháº­n xÃ©t AI vÃ  Ä‘Ã³ng gÃ³i
            ai_analyzer = AISemanticAnalyzer()
            stats_data = {
                "testing_score": testing_result.testing_score,
                "pass_rate": testing_result.pass_rate,
                "critical": testing_result.critical_count,
                "major": testing_result.major_count
            }
            ai_summary = ai_analyzer.generate_executive_summary(stats_data)
            testing_result.ai_summary = ai_summary
            
            result_json = asdict(testing_result)
            
            result_record.status = 'COMPLETED'
            result_record.testing_score = testing_result.testing_score
            result_record.pass_rate = testing_result.pass_rate
            result_record.result_json = result_json
            result_record.save()
            
            from apps.gate_engine.orchestrator import check_and_aggregate
            check_and_aggregate(project_version.id)
            
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
                
    except Exception as e:
        # Avoid breaking if artifact not found, etc.
        try:
            result_record.status = 'FAILED'
            result_record.error_message = str(e)
            result_record.save()
        except:
            pass

