import uuid
from django.db import models

class SourceCodeResultModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_version = models.ForeignKey('projects.ProjectVersion', on_delete=models.CASCADE, db_column='project_version_id')
    artifact = models.ForeignKey('artifacts.Artifact', on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=50, default='PENDING') # PENDING, PROCESSING, COMPLETED, FAILED
    code_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    hard_gate_triggered = models.BooleanField(default=False)
    result_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'source_code_results'
