import uuid
from django.db import models

class AnalysisRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_version = models.ForeignKey('projects.ProjectVersion', on_delete=models.CASCADE, db_column='project_version_id')
    status = models.CharField(max_length=50, default='PENDING')
    testing_weight_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    source_code_weight_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    pass_threshold_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    warning_threshold_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'analysis_runs'

class AnalysisResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    analysis_run = models.ForeignKey(AnalysisRun, on_delete=models.CASCADE, db_column='analysis_run_id')
    testing_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    source_code_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    final_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    decision = models.CharField(max_length=50, null=True, blank=True)
    findings = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analysis_results'
