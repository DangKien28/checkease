from django.db import models

class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True, primary_key=True)
    value = models.TextField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_settings'
