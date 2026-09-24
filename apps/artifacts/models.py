import uuid
from django.db import models

class Artifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project_version = models.ForeignKey('projects.ProjectVersion', on_delete=models.CASCADE, db_column='project_version_id')
    artifact_type = models.CharField(max_length=50)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    sha256 = models.CharField(max_length=64, null=True, blank=True)
    storage_key = models.CharField(max_length=500)
    status = models.CharField(max_length=50, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=100, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'artifacts'

from django.db.models.signals import post_delete
from django.dispatch import receiver
from .minio_client import delete_artifact
import threading

@receiver(post_delete, sender=Artifact)
def artifact_post_delete(sender, instance, **kwargs):
    # Reference counting logic for MinIO Deduplication
    if instance.storage_key:
        count = Artifact.objects.filter(storage_key=instance.storage_key).count()
        if count == 0:
            # Safe to delete physically. Use a thread to avoid blocking DB transaction
            def _delete():
                try:
                    delete_artifact(instance.storage_key)
                except Exception as e:
                    print(f"Failed to delete {instance.storage_key} from MinIO: {e}")
            threading.Thread(target=_delete, daemon=True).start()
