import uuid
from django.db import models

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_id = models.UUIDField()
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    application_tier = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50, default='ACTIVE')
    testing_weight = models.DecimalField(max_digits=5, decimal_places=2, default=0.5)
    source_code_weight = models.DecimalField(max_digits=5, decimal_places=2, default=0.5)
    pass_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=80.0)
    warning_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=60.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'projects'

class ProjectVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, db_column='project_id')
    version_number = models.IntegerField()
    status = models.CharField(max_length=50, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'project_versions'
