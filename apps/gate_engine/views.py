# ==============================================================================
# TÁC GIẢ: Đặng Trung Kiên
# CHI TIẾT: File Views này được tạo mới hoàn toàn bởi Đặng Trung Kiên để xây 
# dựng API cầu nối. Do Nguyễn Tam Trung không code phần API tương thích với 
# Django, Kiên phải viết logic endpoint (`evaluate_gate`, `export_gate_pdf`) 
# kết nối các hàm tổng hợp điểm, xử lý file rác PDF (tempfile), và trả HTTP response.
# ==============================================================================
import json
import tempfile
import os
from pathlib import Path
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from apps.gate_engine.aggregator import GateEngine
from apps.gate_engine.pdf_generator import generate_pdf_report

def _number(value, default=0.0):
    try:
        result = float(value)
        return result if result == result else default
    except (TypeError, ValueError):
        return default

@csrf_exempt
def evaluate_gate(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        
        project_id = payload.get("project_id", "")
        w_test = payload.get("w_test", 0.5)
        w_code = payload.get("w_code", 0.5)
        has_critical = payload.get("has_critical_error", False)
        
        # Pull real source code score from DB if project_id exists
        code_score = 0.0
        try:
            from apps.code_analysis.models import SourceCodeResultModel
            latest_code = SourceCodeResultModel.objects.filter(
                project_version__project_id=project_id,
                status='COMPLETED'
            ).order_by('-created_at').first()
            if latest_code and latest_code.code_score is not None:
                code_score = float(latest_code.code_score)
                if latest_code.hard_gate_triggered:
                    has_critical = True
            else:
                code_score = payload.get("code_score") or payload.get("score_code") or 0.0
        except Exception:
            code_score = payload.get("code_score") or payload.get("score_code") or 0.0
        
        # Pull real testing score from DB if project_id exists
        test_score = 0.0
        try:
            from apps.testing_analysis.models import TestingResultModel
            latest_result = TestingResultModel.objects.filter(
                project_version__project_id=project_id,
                status='COMPLETED'
            ).order_by('-created_at').first()
            if latest_result and latest_result.testing_score is not None:
                test_score = float(latest_result.testing_score)
                # Overwrite has_critical if critical errors exist in testing
                if latest_result.result_json:
                    critical_count = latest_result.result_json.get('critical_count', 0)
                    if critical_count > 0:
                        has_critical = True
            else:
                test_score = payload.get("testing_score") or payload.get("score_test") or 0.0
        except Exception:
            test_score = payload.get("testing_score") or payload.get("score_test") or 0.0
        
        try:
            engine = GateEngine(w_test=w_test, w_code=w_code, pass_threshold=payload.get("pass_threshold", 80.0), warning_threshold=payload.get("warning_threshold", 60.0))
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=422)
            
        errors = [{"severity": "Critical"}] if has_critical else []
        result = engine.evaluate(test_score=test_score, code_score=code_score, errors=errors)
        
        return JsonResponse({
            "project_id": project_id,
            "final_score": round(result.score, 1),
            "verdict": result.verdict,
            "test_score": round(test_score, 1),
            "code_score": round(code_score, 1)
        })
    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def export_gate_pdf(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
            
        project_id = payload.get("project_id", "")
        w_test = payload.get("w_test", 0.5)
        w_code = payload.get("w_code", 0.5)
        has_critical = payload.get("has_critical_error", False)
        report_data = payload.get("report_data", {})
        
        # Pull real source code score from DB if project_id exists
        code_score = 0.0
        try:
            from apps.code_analysis.models import SourceCodeResultModel
            latest_code = SourceCodeResultModel.objects.filter(
                project_version__project_id=project_id,
                status='COMPLETED'
            ).order_by('-created_at').first()
            if latest_code and latest_code.code_score is not None:
                code_score = float(latest_code.code_score)
                if latest_code.hard_gate_triggered:
                    has_critical = True
                if latest_code.result_json:
                    report_data['code_details'] = latest_code.result_json
            else:
                code_score = payload.get("code_score") or payload.get("score_code") or 0.0
        except Exception:
            code_score = payload.get("code_score") or payload.get("score_code") or 0.0
        
        # Pull real testing score from DB if project_id exists
        test_score = 0.0
        try:
            from apps.testing_analysis.models import TestingResultModel
            latest_result = TestingResultModel.objects.filter(
                project_version__project_id=project_id,
                status='COMPLETED'
            ).order_by('-created_at').first()
            if latest_result and latest_result.testing_score is not None:
                test_score = float(latest_result.testing_score)
                if latest_result.result_json:
                    critical_count = latest_result.result_json.get('critical_count', 0)
                    if critical_count > 0:
                        has_critical = True
                    report_data['testing_details'] = latest_result.result_json
            else:
                test_score = payload.get("testing_score") or payload.get("score_test") or 0.0
        except Exception:
            test_score = payload.get("testing_score") or payload.get("score_test") or 0.0
        
        try:
            engine = GateEngine(w_test=w_test, w_code=w_code, pass_threshold=payload.get("pass_threshold", 80.0), warning_threshold=payload.get("warning_threshold", 60.0))
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=422)
            
        errors = [{"severity": "Critical"}] if has_critical else []
        result = engine.evaluate(test_score=test_score, code_score=code_score, errors=errors)
        
        
        try:
            from apps.projects.models import Project, ProjectVersion
            proj = Project.objects.get(id=project_id)
            ver = ProjectVersion.objects.filter(project=proj).order_by('-version_number').first()
            tier_val = 2
            if proj.application_tier and '1' in proj.application_tier: tier_val = 1
            elif proj.application_tier and '3' in proj.application_tier: tier_val = 3
            report_data["project"] = {
                "name": proj.name,
                "tier": tier_val,
                "w_testing": float(proj.testing_weight),
                "w_code": float(proj.source_code_weight)
            }
            if ver:
                from apps.artifacts.models import Artifact
                source_artifacts = Artifact.objects.filter(project_version=ver, artifact_type='SOURCE_CODE')
                test_artifacts = Artifact.objects.filter(project_version=ver, artifact_type='TEST_DOCUMENT')
                
                report_data["version"] = {
                    "seq": ver.version_number,
                    "label": ver.version_name or f"v{ver.version_number}",
                    "source_files": [a.original_filename for a in source_artifacts],
                    "test_files": [a.original_filename for a in test_artifacts]
                }
        except Exception as e:
            pass
        
        # Prepare data for PDF
        
        if 'code_details' in report_data:
            report_data['code'] = report_data.pop('code_details')
        if 'testing_details' in report_data:
            report_data['testing'] = report_data.pop('testing_details')
            
        report_data.update({
            "project_id": project_id,
            "verdict": result.verdict,
            "final_score": result.score,
            "test_score": test_score,
            "testing_score": test_score,
            "code_score": code_score,
        })
        
        # Generate temporary PDF file
        from django.conf import settings
        project_tmp_dir = os.path.join(settings.BASE_DIR, 'tmp')
        os.makedirs(project_tmp_dir, exist_ok=True)
        fd, output_path = tempfile.mkstemp(prefix="checkease_", suffix=".pdf", dir=project_tmp_dir)
        os.close(fd)
        
        try:
            generate_pdf_report(report_data, output_path)
            # Using FileResponse will automatically close the file, but we need to delete it.
            # Django's FileResponse doesn't delete the file automatically.
            # In a real app we might use a background task or a custom cleanup. 
            # We'll just open it and pass to FileResponse.
            file_obj = open(output_path, 'rb')
            response = FileResponse(file_obj, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="Checkease_Release_Report.pdf"'
            return response
        except Exception as e:
            if os.path.exists(output_path):
                os.unlink(output_path)
            return JsonResponse({"error": str(e)}, status=500)
            
    return JsonResponse({"error": "Method not allowed"}, status=405)
